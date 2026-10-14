#!/usr/bin/env python3
"""Rebuild on every save and serve dist/web. The page reloads itself when the build changes.
Open http://localhost:8000, or http://<this-computer's-LAN-IP>:8000 on the tablet."""
import http.server, os, socket, socketserver, subprocess, sys, threading, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB, DIST = os.path.join(ROOT, "web"), os.path.join(ROOT, "dist", "web")
PORT = int(os.environ.get("PORT", 8000))
stamp = {"v": 0}
RELOAD = "<script>(function(){let v=null;setInterval(async()=>{try{const r=await fetch('/__version');const t=await r.text();if(v&&t!==v)location.reload();v=t}catch(e){}},800)})()</script>"

def snapshot():
    out = {}
    for d, _, files in os.walk(WEB):
        for f in files:
            p = os.path.join(d, f); out[p] = os.path.getmtime(p)
    return out

def build():
    r = subprocess.run([sys.executable, os.path.join(WEB, "build.py")], capture_output=True, text=True)
    print(time.strftime("%H:%M:%S"), "build", "ok" if r.returncode == 0 else "FAILED\n" + r.stderr, flush=True)
    stamp["v"] += 1

def watch():
    last = snapshot()
    while True:
        time.sleep(0.5); now = snapshot()
        if now != last: last = now; build()

class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=DIST, **k)
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path == "/__version":
            b = str(stamp["v"]).encode(); self.send_response(200); self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b); return
        if self.path in ("/", "/index.html"):
            html = open(os.path.join(DIST, "index.html"), encoding="utf-8").read().replace("</body>", RELOAD + "</body>").encode()
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(html))); self.end_headers(); self.wfile.write(html); return
        super().do_GET()

if __name__ == "__main__":
    build(); threading.Thread(target=watch, daemon=True).start()
    try:
        u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); u.connect(("10.255.255.255", 1)); ip = u.getsockname()[0]; u.close()
    except Exception: ip = "<this-computer's-ip>"
    print(f"Serving on http://localhost:{PORT}  (tablet: http://{ip}:{PORT})  Ctrl+C to stop", flush=True)
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), H) as s: s.serve_forever()
