import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from http.server import BaseHTTPRequestHandler
from _rbx import *


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        d = read_json(self)
        ck = dec(d.get("ck"))
        if not ck.get("RBXSID"):
            return send(self, 200, {"ok": False, "error": "sin cookies RBXSID"})
        url = (d.get("url") or "").strip()
        pid = d.get("pid") or 0
        price = d.get("price") or 0
        seller = d.get("seller") or 0
        s = new_session(ck, d.get("ua"))
        ok, msg, endpoint = buy(s, url, pid, price, seller, d.get("curl") or "")
        if ok:
            send(self, 200, {"ok": True, "endpoint": endpoint, "msg": msg})
        else:
            send(self, 200, {"ok": False, "error": msg})

    def log_message(self, *a):
        pass
