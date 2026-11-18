import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))
from http.server import BaseHTTPRequestHandler
import requests


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("content-length") or 0)
        try:
            import json
            d = json.loads(self.rfile.read(n).decode() or "{}")
        except Exception:
            return self._out(200, {"ok": False, "error": "json invalido"})

        hook = (d.get("hook") or "").strip()
        payload = d.get("payload") or {}
        if not hook.startswith("https://discord.com/api/webhooks/"):
            return self._out(200, {"ok": False, "error": "webhook invalido"})

        last = ""
        for _ in range(3):
            try:
                r = requests.post(hook, json=payload, timeout=12)
                if r.status_code == 429:
                    try:
                        time.sleep(float(r.json().get("retry_after", 1.5)) + .2)
                    except Exception:
                        time.sleep(1.5)
                    continue
                if r.status_code >= 500:
                    time.sleep(1)
                    continue
                return self._out(200, {"ok": r.status_code < 300, "status": r.status_code})
            except Exception as e:
                last = str(e)
                time.sleep(0.6)
        self._out(200, {"ok": False, "error": last or "fallo el envio"})

    def _out(self, code, obj):
        import json
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("access-control-allow-origin", "*")
        self.send_header("content-length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):
        pass
