"""Núcleo compartido: sesión con fingerprint, parseo y compra."""
import base64, json, re
import requests
try:
    from curl_cffi import requests as cffi
except Exception:
    cffi = None

BASE = "https://www.rokori.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

CARD_RE = re.compile(r'href="/catalog/(\d+)/([^"]*)"')
ALT_RE = re.compile(r'alt="([^"]{2,90})"')
DPRICE_RE = re.compile(r'data-(?:price|expected-price|lowest-price)="(\d+)"')
TXT_RE = re.compile(r'text-robux[^>]*>\s*([\d,]+)')
ROBUX_RE = re.compile(r'([\d][\d,]{0,11})\s*(?:Robux|R\$)')
FREE_RE = re.compile(r'\b(?:free|gratis|gratuit)\b', re.I)
IMG_RE = re.compile(r'((?:https://www\.rokori\.com)?/thumbnails?/[^"\'\s]+|https://[^"\'\s]+\.(?:png|jpg|jpeg|webp))')

CANDIDATES = [
    BASE + "/apis/v1/purchases/products/{pid}",
    BASE + "/apis/purchases/products/{pid}",
    BASE + "/apis/v1/purchase/{pid}",
    BASE + "/apis/v1/catalog/purchase",
]
LOGINS = [
    (BASE + "/apis/v1/auth/login", "json", "plain"),
    (BASE + "/apis/login", "json", "plain"),
    (BASE + "/v2/login", "json", "v2"),
    (BASE + "/login", "form", "plain"),
]
AUTH_CHECKS = ["/apis/v1/users/authenticated", "/apis/v1/auth/me", "/apis/me"]


def dec(header):
    if not header:
        return {}
    try:
        return json.loads(base64.b64decode(header + "==="))
    except Exception:
        return {}


def send(h, code, obj):
    body = json.dumps(obj, ensure_ascii=False).encode()
    h.send_response(code)
    h.send_header("content-type", "application/json; charset=utf-8")
    h.send_header("cache-control", "no-store")
    h.send_header("access-control-allow-origin", "*")
    h.send_header("content-length", str(len(body)))
    h.end_headers()
    h.wfile.write(body)


def read_json(h):
    try:
        n = int(h.headers.get("content-length") or 0)
        if not n:
            return {}
        return json.loads(h.rfile.read(n).decode() or "{}")
    except Exception:
        return {}


def new_session(cookies=None, ua=None):
    if cffi:
        try:
            s = cffi.Session(impersonate="chrome131")
        except Exception:
            s = requests.Session()
    else:
        s = requests.Session()
    s.headers.update({
        "user-agent": ua or UA,
        "accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8",
        "accept-language": "es-ES,es;q=0.9",
        "referer": BASE + "/",
    })
    for k, v in (cookies or {}).items():
        try:
            s.cookies.set(k, str(v), domain="www.rokori.com")
        except Exception:
            pass
    return s


def parse_cards(html):
    out = {}
    for m in CARD_RE.finditer(html):
        iid, slug = int(m.group(1)), m.group(2)
        w = html[max(0, m.start() - 2500): m.end() + 2500]
        a = ALT_RE.search(w)
        name = (a.group(1).strip() if a else "") or slug.replace("-", " ").strip() or f"item {iid}"
        price = None
        for rx in (DPRICE_RE, TXT_RE, ROBUX_RE):
            g = rx.search(w)
            if g:
                try:
                    price = int(g.group(1).replace(",", ""))
                except Exception:
                    price = None
                break
        if price is None and FREE_RE.search(w):
            price = 0
        im = IMG_RE.search(w)
        out.setdefault(iid, {
            "id": iid, "name": name, "price": price,
            "img": im.group(1) if im else None,
            "url": f"{BASE}/catalog/{iid}/{slug}",
        })
    return list(out.values())


def csrf(s):
    try:
        r = s.get(BASE + "/login", timeout=20)
        m = re.search(r'name="csrf-token"\s+content="([^"]+)"', r.text)
        return m.group(1) if m else r.headers.get("x-csrf-token")
    except Exception:
        return None


def details(s, url):
    d = {"pid": None, "seller": None, "price": None}
    try:
        t = s.get(url, timeout=20).text
        for k, rx in (
            ("pid", r'"(?:collectibleProductId|productId)"\s*:\s*(\d+)'),
            ("pid", r'data-(?:product|collectible-product)-id="(\d+)"'),
            ("seller", r'"(?:expectedSellerId|sellerId)"\s*:\s*(\d+)'),
            ("price", r'"(?:lowestResalePrice|lowestPrice|price)"\s*:\s*(\d+)'),
        ):
            g = re.search(rx, t)
            if g and not d[k]:
                d[k] = int(g.group(1))
    except Exception:
        pass
    return d


def whoami(s):
    for p in AUTH_CHECKS:
        try:
            r = s.get(BASE + p, timeout=10)
            if r.status_code == 200 and r.text.strip().startswith("{"):
                d = r.json()
                for k in ("name", "username", "displayName", "user"):
                    v = d.get(k)
                    if isinstance(v, dict):
                        v = v.get("name") or v.get("username")
                    if v:
                        return str(v)
        except Exception:
            pass
    return None


def is_auth(s):
    if whoami(s):
        return True
    try:
        r = s.get(BASE + "/catalog", timeout=15)
        if r.status_code != 200:
            return False
        t = r.text.lower()
        if "sign up" in t or 'href="/login"' in t:
            return False
        return bool(s.cookies.get("RBXSID"))
    except Exception:
        return False


def parse_curl(tpl, pid, price, seller):
    import shlex
    parts = shlex.split(tpl.replace("\\\n", " "))
    url = next((x for x in parts if x.startswith("http")), "")
    hdr, body = {}, ""
    for i, x in enumerate(parts):
        if x in ("-H", "--header") and i + 1 < len(parts):
            k, _, v = parts[i + 1].partition(":")
            hdr[k.strip()] = v.strip()
        if x in ("--data-raw", "--data", "-d") and i + 1 < len(parts):
            body = parts[i + 1]
    sub = lambda t: t.replace("{pid}", str(pid)).replace("{price}", str(price)).replace("{seller}", str(seller))
    return sub(url), hdr, sub(body)


def buy(s, it_url, pid, price, seller, curl_tpl=""):
    hdr = {
        "x-csrf-token": csrf(s) or "",
        "content-type": "application/json",
        "origin": BASE,
        "referer": it_url,
        "accept": "application/json, text/plain, */*",
    }
    if curl_tpl:
        u, extra, body = parse_curl(curl_tpl, pid, price, seller)
        hdr.update(extra)
        plan = [(u, hdr, body)]
    else:
        body = json.dumps({
            "expectedCurrency": 1,
            "expectedPrice": price,
            "expectedSellerId": seller or 0,
        })
        plan = [(u.format(pid=pid), hdr, body) for u in CANDIDATES]

    last = "sin respuesta"
    for u, h, b in plan:
        for attempt in (1, 2):
            try:
                r = s.post(u, headers=h, data=b, timeout=20)
            except Exception as e:
                last = f"red: {e}"
                break
            if r.status_code == 403 and attempt == 1 and r.headers.get("x-csrf-token"):
                h["x-csrf-token"] = r.headers["x-csrf-token"]
                continue
            try:
                data = r.json()
            except Exception:
                data = {}
            if r.ok and (data.get("purchased") is True
                         or str(data.get("status", "")).lower() in ("purchased", "success")):
                return True, data, u
            last = json.dumps(data, ensure_ascii=False)[:400] if data else f"HTTP {r.status_code}"
            if r.status_code in (404, 405):
                break
    return False, last, None
