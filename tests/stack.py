"""Test helper: a fake Azure (OpenAI chat + images + Speech) and a real Spell Car server pointed at it."""
import base64, io, json, os, socket, struct, subprocess, sys, threading, time, urllib.request, wave, zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY, TOKEN = "fake-azure-key", "test-token-0123456789abcdef"

def png(w=8, h=6, rgb=(140, 80, 230)):
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")

def wav(ms=250):
    b = io.BytesIO(); w = wave.open(b, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
    w.writeframes(b"\x00\x00" * int(16 * ms)); w.close(); return b.getvalue()

class FakeAzure(BaseHTTPRequestHandler):
    seen = []
    def log_message(self, *a): pass
    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0)); FakeAzure.seen.append((self.path, body))
        if "/cognitiveservices/v1" in self.path:
            if self.headers.get("Ocp-Apim-Subscription-Key") != KEY: return self.send(401, {"error": "key"})
            assert b"<voice name=" in body
            return self.send(200, wav(), "audio/wav")
        if self.headers.get("api-key") != KEY: return self.send(401, {"error": {"code": "401"}})
        req = json.loads(body)
        if "/chat/completions" in self.path:
            if "max_completion_tokens" in req and "temperature" in req:   # simulate a model that rejects temperature
                return self.send(400, {"error": {"code": "unsupported_parameter", "message": "temperature"}})
            prompt = req["messages"][1]["content"]
            if "FILTERME" in prompt: return self.send(400, {"error": {"code": "content_filter", "message": "filtered"}})
            return self.send(200, {"choices": [{"finish_reason": "stop", "message": {"role": "assistant",
                "content": "The Sparkle Parade\n\nLuna and her friends went to the castle. Everyone smiled.\n\nLuna counted one blue and one red mana. Sparkle! The end."}}]})
        if "/images/generations" in self.path:
            return self.send(200, {"data": [{"b64_json": base64.b64encode(png()).decode()}]})
        self.send(404, {"error": "nope"})

def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

class Stack:
    def __init__(self, **limits):
        self.az_port, self.port = free_port(), free_port()
        self.az = ThreadingHTTPServer(("127.0.0.1", self.az_port), FakeAzure)
        threading.Thread(target=self.az.serve_forever, daemon=True).start()
        az = f"http://127.0.0.1:{self.az_port}"
        env = {**os.environ, "SPELLCAR_TOKEN": TOKEN, "AZURE_OPENAI_ENDPOINT": az, "AZURE_OPENAI_KEY": KEY,
               "AZURE_OPENAI_CHAT_DEPLOYMENT": "chat", "AZURE_OPENAI_IMAGE_DEPLOYMENT": "img", "AZURE_SPEECH_KEY": KEY,
               "AZURE_SPEECH_ENDPOINT": az + "/cognitiveservices/v1", "PORT": str(self.port), **{k: str(v) for k, v in limits.items()}}
        self.proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "server", "spellcar_server.py")], env=env,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.url = f"http://127.0.0.1:{self.port}"
        for _ in range(50):
            try: urllib.request.urlopen(self.url + "/nope", timeout=0.3)
            except urllib.error.HTTPError: break
            except Exception: time.sleep(0.1)
    def close(self):
        self.proc.terminate(); self.proc.wait(5); self.az.shutdown()
