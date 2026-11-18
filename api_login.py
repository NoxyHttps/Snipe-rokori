import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from http.server import BaseHTTPRequestHandler
from urllib.parse import urljoin
import re
from _rbx import *


def find_form(html):
    for m in re.finditer(r"<form[^>]*>", html, re.I):
        end = html.find("</form>", m.start())
        block = html[m.start(): end if end > 0 else m.start() + 5000]
        am = re.search(r'action="([^"]*)"', m.group(0))
        mm = re.search(r'method="([^"]*)"', m.group(0))
        fields, ident, pwd = {}, None, None
        for inp in re.findall(r"<input[^>]*>", block, re.I):
            nm = re.search(r'name="([^"]+)"', inp)
            tp = re.search(r'type="([^"]+)"', inp)
            vl = re.search(r'value="([^"]*)"', inp)
            if not nm:
                continue
            name, typ = nm.group(1), (tp.group(1).lower() if tp else "text")
            fields[name] = vl.group(1) if vl else ""
            if typ == "password":
                pwd = name
            elif typ in ("text", "email") or re.search(r"user|login|mail|name", name, re.I):
                ident = ident or name
        if pwd and ident:
            return (am.group(1) if am else "", (mm.group(1).lower() if mm else "post"), fields, ident, pwd)
    return None


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        d = read_json(self)
        u = (d.get("user") or "").strip()
        p = d.get("pass") or ""
        code = (d.get("twofa") or "").strip()
        if not u or not p:
            return send(self, 200, {"ok": False, "error": "faltan usuario/password"})

        s = new_session()
        base_hdr = {"origin": BASE, "referer": BASE + "/login",
                    "accept": "text/html,application/json,*/*"}
        tok = csrf(s)

        # 1) form real
        try:
            page = s.get(BASE + "/login", timeout=20)
        except Exception:
            page = None
        if page is not None and page.ok:
            f = find_form(page.text)
            if f:
                action, method, fields, ident, pwd = f
                url = urljoin(BASE + "/login", action or BASE + "/login")
                data = dict(fields)
                data[ident] = u
                data[pwd] = p
                hdr = {**base_hdr, "content-type": "application/x-www-form-urlencoded"}
                if tok:
                    hdr["x-csrf-token"] = tok
                try:
                    r = s.post(url, data=data, headers=hdr, timeout=20)
                    if r.status_code < 400 and is_auth(s):
                        return send(self, 200, {"ok": True, "cookies": s.cookies.get_dict()})
                except Exception:
                    pass

        # 2) endpoints JSON
        hdr = {**base_hdr, "x-csrf-token": tok or "",
               "accept": "application/json, text/plain, */*"}
        last = "sin respuesta"
        for url, kind, mode in LOGINS:
            payload = ({"ctype": "Username", "cvalue": u, "password": p}
                       if mode == "v2" else {"username": u, "password": p})
            if code:
                payload["code"] = code
                payload["twoFactorCode"] = code
            try:
                if kind == "json":
                    r = s.post(url, json=payload,
                               headers={**hdr, "content-type": "application/json"}, timeout=20)
                else:
                    r = s.post(url, data=payload, headers=hdr, timeout=20)
            except Exception as e:
                last = f"{url}: {e}"
                continue
            if r.status_code in (404, 405):
                continue
            if r.status_code < 400 and is_auth(s):
                return send(self, 200, {"ok": True, "cookies": s.cookies.get_dict()})
            last = f"{url} HTTP {r.status_code}: {r.text[:180]}"
            if r.status_code in (400, 401, 403):
                break

        send(self, 200, {"ok": False, "error": last[:300]})

    def log_message(self, *a):
        pass