"""Test helper: a fake Azure (OpenAI chat + images + Speech) and a real Spell Car server pointed at it."""
import base64, io, json, os, socket, struct, subprocess, sys, tempfile, threading, time, urllib.request, wave, zlib
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

CLIP = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fake_clip.webm"), "rb").read()

class FakeAzure(BaseHTTPRequestHandler):
    """Fakes Azure OpenAI, Azure Speech, and Google Veo (Gemini API long-running operations)."""
    seen = []
    polls = {}
    edits_ok = True
    def log_message(self, *a): pass
    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0)); FakeAzure.seen.append((self.path, body))
        if ":predictLongRunning" in self.path:
            if self.headers.get("x-goog-api-key") != KEY: return self.send(401, {"error": {"code": 401}})
            inst = json.loads(body)["instances"][0]
            assert "inlineData" in inst["image"] and "comes to life" in inst["prompt"]
            n = len(FakeAzure.polls); FakeAzure.polls[f"op{n}"] = 0
            return self.send(200, {"name": f"operations/op{n}"})
        if "/cognitiveservices/v1" in self.path:
            if self.headers.get("Ocp-Apim-Subscription-Key") != KEY: return self.send(401, {"error": "key"})
            assert b"<voice name=" in body
            return self.send(200, wav(), "audio/wav")
        if "/images/edits" in self.path:
            if self.headers.get("api-key") != KEY: return self.send(401, {"error": {"code": "401"}})
            if not FakeAzure.edits_ok: return self.send(400, {"error": {"code": "OperationNotSupported", "message": "image edits not supported by this model"}})
            ct = self.headers.get("Content-Type", "")
            has_img = b"\x89PNG" in body or b"\xff\xd8\xff" in body
            assert ct.startswith("multipart/form-data") and b'name="prompt"' in body and b'name="image' in body and has_img, "bad multipart"
            return self.send(200, {"data": [{"b64_json": base64.b64encode(png(12, 8, (240, 180, 90))).decode()}]})
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
    def do_GET(self):
        if self.headers.get("x-goog-api-key") != KEY: return self.send(401, {"error": {"code": 401}})
        if "/operations/" in self.path:
            op = self.path.rsplit("/", 1)[1]; FakeAzure.polls[op] = FakeAzure.polls.get(op, 0) + 1
            if FakeAzure.polls[op] < 2: return self.send(200, {"name": "operations/" + op, "done": False})
            base = f"http://127.0.0.1:{self.server.server_address[1]}"
            return self.send(200, {"name": "operations/" + op, "done": True, "response": {"generateVideoResponse": {
                "generatedSamples": [{"video": {"uri": f"{base}/v1beta/files/{op}:download?alt=media"}}]}}})
        if "/files/" in self.path: return self.send(200, CLIP, "video/webm")
        self.send(404, {"error": "nope"})

def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

class Stack:

    """SPELLCAR_IMPL=worker runs the Cloudflare Worker (wrangler dev, local KV/R2) instead of the Python server."""
    def __init__(self, **limits):
        self.az_port, self.port = free_port(), free_port()
        self.az = ThreadingHTTPServer(("127.0.0.1", self.az_port), FakeAzure)
        threading.Thread(target=self.az.serve_forever, daemon=True).start()
        az = f"http://127.0.0.1:{self.az_port}"
        env = {**os.environ, "SPELLCAR_TOKEN": TOKEN, "AZURE_OPENAI_ENDPOINT": az, "AZURE_OPENAI_KEY": KEY,
               "AZURE_OPENAI_CHAT_DEPLOYMENT": "chat", "AZURE_OPENAI_IMAGE_DEPLOYMENT": "img", "AZURE_SPEECH_KEY": KEY,
               "AZURE_SPEECH_ENDPOINT": az + "/cognitiveservices/v1", "PORT": str(self.port),
               "GEMINI_API_KEY": KEY, "VEO_BASE": az + "/v1beta", "VEO_POLL_SECONDS": "0.3", "VIDEO_DIR": tempfile.mkdtemp(prefix="spellcar-videos-"), **{k: str(v) for k, v in limits.items()}}
        # Rootha's shorts: a real list with one bad id and one entry whose movie is missing (both must be dropped).
        shorts = env["SHORTS_DIR"] = tempfile.mkdtemp(prefix="spellcar-shorts-")
        json.dump([{"id": "film", "title": "Rootha's big movie"}, {"id": "hello", "title": "Hello <b>from</b> Rootha"},
                   {"id": "../bad", "title": "Sneaky"}, {"id": "gone", "title": "Missing movie"}], open(os.path.join(shorts, "index.json"), "w"))
        for name, data in (("film.mp4", CLIP), ("film.jpg", png(32, 18)), ("hello.mp4", CLIP)):
            with open(os.path.join(shorts, name), "wb") as f: f.write(data)
        self.impl = os.environ.get("SPELLCAR_IMPL", "python")
        if self.impl == "worker":
            wd = os.path.join(ROOT, "worker"); skip = {"PORT", "VIDEO_DIR", "SHORTS_DIR", "VEO_POLL_SECONDS"}
            persist = tempfile.mkdtemp(prefix="spellcar-wrangler-")
            for name in sorted(os.listdir(shorts)):  # the same shorts, in the worker's local R2
                ctype = {"json": "application/json", "jpg": "image/jpeg"}.get(name.rsplit(".", 1)[1], "video/webm")
                subprocess.run(["npx", "wrangler", "r2", "object", "put", f"spellcar-clips/shorts/{name}", "--local", "--persist-to", persist,
                                "--file", os.path.join(shorts, name), "--content-type", ctype], cwd=wd, check=True,
                               env={**os.environ, "WRANGLER_SEND_METRICS": "false", "CI": "1"}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            keys = [k for k in env if k.startswith(("SPELLCAR_", "AZURE_", "GEMINI_", "VEO_")) or k.endswith("_PER_DAY")]
            args = sum((["--var", f"{k}:{env[k]}"] for k in keys if k not in skip), [])
            self.proc = subprocess.Popen(["npx", "wrangler", "dev", "--test-scheduled", "--ip", "127.0.0.1", "--port", str(self.port),
                                          "--persist-to", persist, *args],
                                         cwd=wd, env={**os.environ, "WRANGLER_SEND_METRICS": "false", "CI": "1"},
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            tries = 300
        else:
            self.proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "server", "spellcar_server.py")], env=env,
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            tries = 50
        self.url = f"http://127.0.0.1:{self.port}"
        for _ in range(tries):
            try: urllib.request.urlopen(self.url + "/nope", timeout=0.3)
            except urllib.error.HTTPError: break
            except Exception: time.sleep(0.1)
    def close(self):
        self.proc.terminate(); self.proc.wait(5); self.az.shutdown()
