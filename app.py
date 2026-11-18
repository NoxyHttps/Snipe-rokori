import os
import sys
import time
from urllib.parse import urljoin

import requests
from flask import Flask, jsonify, request, send_from_directory

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "api"))

import _rbx as R
import login as login_mod

app = Flask(__name__, static_folder=None)


def body():
    return request.get_json(silent=True) or {}


def ck():
    return R.dec(body().get("ck"))


def ua():
    return body().get("ua")


@app.get("/")
@app.get("/index.html")
def index():
    return send_from_directory(HERE, "index.html")


@app.route("/api/catalog", methods=["GET", "POST"])
def catalog():
    d = body()
    url = (d.get("url") or "").strip() or (R.BASE + "/catalog")
    s = R.new_session(ck(), ua())
    try:
        r = s.get(url, timeout=25)
    except Exception as e:
        return jsonify(ok=False, error=f"red: {e}")
    if not r.ok:
        return jsonify(ok=False, error=f"catalogo HTTP {r.status_code}")
    items = R.parse_cards(r.text)
    low = r.text.lower()
    auth = bool(s.cookies.get("RBXSID")) and not ("sign up" in low and 'href="/login"' in low)
    return jsonify(ok=True, items=items, count=len(items), auth=auth)


@app.post("/api/item")
def item():
    url = (body().get("url") or "").strip()
    if not url:
        return jsonify(ok=False, error="falta url")
    s = R.new_session(ck(), ua())
    return jsonify(ok=True, **R.details(s, url))


@app.post("/api/buy")
def buy():
    d = body()
    c = ck()
    if not c.get("RBXSID"):
        return jsonify(ok=False, error="sin cookies RBXSID")
    s = R.new_session(c, ua())
    ok, msg, ep = R.buy(
        s,
        (d.get("url") or "").strip(),
        d.get("pid") or 0,
        d.get("price") or 0,
        d.get("seller") or 0,
        d.get("curl") or "",
    )
    if ok:
        return jsonify(ok=True, endpoint=ep, msg=msg)
    return jsonify(ok=False, error=msg)


@app.post("/api/whoami")
def whoami():
    c = ck()
    if not c.get("RBXSID"):
        return jsonify(ok=False, error="sin RBXSID")
    s = R.new_session(c, ua())
    user = R.whoami(s)
    if user:
        return jsonify(ok=True, user=user)
    if R.is_auth(s):
        return jsonify(ok=True, user=None)
    return jsonify(ok=False, error="sesion invalida o expirada")


@app.post("/api/login")
def login():
    d = body()
    u = (d.get("user") or "").strip()
    p = d.get("pass") or ""
    code = (d.get("twofa") or "").strip()
    if not u or not p:
        return jsonify(ok=False, error="faltan usuario/password")

    s = R.new_session()
    base_hdr = {"origin": R.BASE, "referer": R.BASE + "/login"}
    tok = R.csrf(s)

    try:
        page = s.get(R.BASE + "/login", timeout=20)
    except Exception:
        page = None

    if page is not None and page.ok:
        f = login_mod.find_form(page.text)
        if f:
            action, method, fields, ident, pwd = f
            url = urljoin(R.BASE + "/login", action or R.BASE + "/login")
            data = dict(fields)
            data[ident] = u
            data[pwd] = p
            hdr = {**base_hdr, "content-type": "application/x-www-form-urlencoded"}
            if tok:
                hdr["x-csrf-token"] = tok
            try:
                s.post(url, data=data, headers=hdr, timeout=20)
                if R.is_auth(s):
                    return jsonify(ok=True, cookies=s.cookies.get_dict())
            except Exception:
                pass

    hdr = {**base_hdr, "x-csrf-token": tok or "", "accept": "application/json, text/plain, */*"}
    last = "sin respuesta"
    for url, kind, mode in R.LOGINS:
        payload = (
            {"ctype": "Username", "cvalue": u, "password": p}
            if mode == "v2"
            else {"username": u, "password": p}
        )
        if code:
            payload["code"] = code
            payload["twoFactorCode"] = code
        try:
            if kind == "json":
                r = s.post(url, json=payload, headers={**hdr, "content-type": "application/json"}, timeout=20)
            else:
                r = s.post(url, data=payload, headers=hdr, timeout=20)
        except Exception as e:
            last = f"{url}: {e}"
            continue
        if r.status_code in (404, 405):
            continue
        if r.status_code < 400 and R.is_auth(s):
            return jsonify(ok=True, cookies=s.cookies.get_dict())
        last = f"{url} HTTP {r.status_code}: {r.text[:180]}"
        if r.status_code in (400, 401, 403):
            break

    return jsonify(ok=False, error=last[:300])


@app.post("/api/webhook")
def webhook():
    d = body()
    hook = (d.get("hook") or "").strip()
    payload = d.get("payload") or {}
    if not hook.startswith("https://discord.com/api/webhooks/"):
        return jsonify(ok=False, error="webhook invalido")

    last = ""
    for _ in range(3):
        try:
            r = requests.post(hook, json=payload, timeout=12)
            if r.status_code == 429:
                try:
                    time.sleep(float(r.json().get("retry_after", 1.5)) + 0.2)
                except Exception:
                    time.sleep(1.5)
                continue
            if r.status_code >= 500:
                time.sleep(1)
                continue
            return jsonify(ok=r.status_code < 300, status=r.status_code)
        except Exception as e:
            last = str(e)
            time.sleep(0.6)
    return jsonify(ok=False, error=last or "fallo el envio")
