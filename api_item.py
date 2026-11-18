import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from http.server import BaseHTTPRequestHandler
from _rbx import *


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        d = read_json(self)
        url = (d.get("url") or "").strip()
        if not url:
            return send(self, 200, {"ok": False, "error": "falta url"})
        s = new_session(dec(d.get("ck")), d.get("ua"))
        det = details(s, url)
        send(self, 200, {"ok": True, **det})

    def log_message(self, *a):
        pass