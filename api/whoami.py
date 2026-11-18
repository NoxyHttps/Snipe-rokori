import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from http.server import BaseHTTPRequestHandler
from _rbx import *


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        d = read_json(self)
        ck = dec(d.get("ck"))
        if not ck.get("RBXSID"):
            return send(self, 200, {"ok": False, "error": "sin RBXSID"})
        s = new_session(ck, d.get("ua"))
        user = whoami(s)
        if user:
            return send(self, 200, {"ok": True, "user": user})
        if is_auth(s):
            return send(self, 200, {"ok": True, "user": None})
        send(self, 200, {"ok": False, "error": "sesion invalida o expirada"})

    def log_message(self, *a):
        pass
