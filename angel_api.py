import os, time, hmac, hashlib, struct, base64, requests

LOGIN_URL = "https://apiconnect.angelone.in/rest/auth/angelbroking/user/v1/loginByPassword"
RMS_URL = "https://apiconnect.angelone.in/rest/secure/angelbroking/user/v1/getRMS"

def _totp(sec):
    s = sec.replace(" ", "").upper()
    s += "=" * ((8 - len(s) % 8) % 8)
    k = base64.b32decode(s)
    m = struct.pack(">Q", int(time.time() // 30))
    h = hmac.new(k, m, hashlib.sha1).digest()
    o = h[-1] & 0x0F
    return f"{(struct.unpack('>I', h[o:o+4])[0] & 0x7FFFFFFF) % 1000000:06d}"

def _hdr(api_key, jwt=None):
    h = {
        "Content-Type": "application/json", "Accept": "application/json",
        "X-UserType": "USER", "X-SourceID": "WEB",
        "X-ClientLocalIP": "127.0.0.1", "X-ClientPublicIP": "185.155.223.42",
        "X-MACAddress": "00:00:00:00:00:00", "X-PrivateKey": api_key,
    }
    if jwt: h["Authorization"] = f"Bearer {jwt}"
    return h

def test_angel_login():
    ak = os.environ.get("ANGEL_API_KEY", "").strip()
    cc = os.environ.get("ANGEL_CLIENT_CODE", "").strip()
    pin = os.environ.get("ANGEL_PIN", "").strip()
    totp_sec = os.environ.get("ANGEL_TOTP_SECRET", "").strip()
    px = os.environ.get("STATIC_PROXY_URL", "").strip()
    if not all([ak, cc, pin, totp_sec, px]):
        return "Angel One: Env vars missing"
    proxies = {"http": px, "https": px}
    try:
        r = requests.post(LOGIN_URL, headers=_hdr(ak), json={"clientcode": cc, "password": pin, "totp": _totp(totp_sec), "state": "live"}, proxies=proxies, timeout=15).json()
        if not r.get("status"):
            return f"Angel Login Err: {r.get('message', r)}"
        jwt = r["data"]["jwtToken"]
        rms = requests.get(RMS_URL, headers=_hdr(ak, jwt), proxies=proxies, timeout=15).json()
        net = float(rms.get("data", {}).get("net", 0))
        return f"Angel One: CONNECTED (Static IP)\nReal Balance: ₹{net:,.2f}"
    except Exception as e:
        return f"Angel Conn Err: {e}"
