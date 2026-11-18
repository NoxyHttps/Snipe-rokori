import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from http.server import BaseHTTPRequestHandler
from _rbx import *


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.do_POST()

    def do_POST(self):
        d = read_json(self)
        url = (d.get("url") or "").strip() or (BASE + "/catalog")
        s = new_session(dec(d.get("ck")), d.get("ua"))
        try:
            r = s.get(url, timeout=25)
        except Exception as e:
            return send(self, 200, {"ok": False, "error": f"red: {e}"})
        if not r.ok:
            return send(self, 200, {"ok": False, "error": f"catalogo HTTP {r.status_code}"})
        items = parse_cards(r.text)
        low = r.text.lower()
        auth = bool(s.cookies.get("RBXSID")) and not ("sign up" in low and 'href="/login"' in low)
        send(self, 200, {"ok": True, "items": items, "count": len(items), "auth": auth})

    def log_message(self, *a):
        pass
