# -*- coding: utf-8 -*-
# DEVELOPER: ERIS
import sys, asyncio, httpx, random, json, socket, struct, time, os, uuid, math, itertools
from datetime import datetime
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from aiogram import Bot as TgBot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# ═══════════════════════════ CONFIG ═══════════════════════════
WEB_PORT = 20333
TOKEN_CACHE_FILE = "token_cache.json"
DEVICES_FILE = "devices.json"
TOKEN_CACHE_TTL = 86400

START_MATCH_INTERVAL, NEW_MATCH_DELAY = 4.0, 8.0
MAX_MATCH_DURATION, MATCH_IDLE_TIMEOUT = 3000, 90.0
DEATH_WAIT_SECONDS, MATCH_END_WAIT_SECONDS = 120.0, 60.0
TEAM_MODE, TEAM_SIZE = True, 4
TEAM_PEER_WAIT_TIMEOUT, TEAM_CREATE_WAIT = 120.0, 4.0
TEAM_INVITE_CYCLE_WAIT, TEAM_INVITE_MAX_TIME = 4.0, 120.0
TEAM_HEARTBEAT_INTERVAL, TEAM_IDLE_ITERS_TEAM = 3.0, 3600
TEAM_MEMBER_START_DELAY, TEAM_FINAL_WAIT, TEAM_READY_DELAY = 25.0, 8.0, 5.0
_accept_friend_request = True
GUILD_UID = "3055649830"
GUILD_LEADER_UID = "1393415350"
FALLBACK_CLIENT_VERSION = "1.132.11"
FALLBACK_CLIENT_VERSION_CODE = "2019121229"

TG_TOKEN = "8839167099:AAHuY9084drJns-pjJ3tgqzAMKnocVJC4e4"
ADMIN_ID = 7424554376

class Colors: GREEN='\033[92m'; FAIL='\033[91m'; WARNING='\033[93m'; CYAN='\033[96m'; MAGENTA='\033[95m'; WHITE='\033[97m'; ENDC='\033[0m'
def print_colored(t, c=Colors.WHITE):
    try: print(f"{c}{t}{Colors.ENDC}", flush=True)
    except Exception: pass
def print_success(t): print_colored(f"[+] {t}", Colors.GREEN)
def print_error(t): print_colored(f"[-] {t}", Colors.FAIL)
def print_warning(t): print_colored(f"[!] {t}", Colors.WARNING)
def print_info(t): print_colored(f"[i] {t}", Colors.CYAN)

HARDCODED_ACCOUNTS = [
    {"uid": "8289010389", "password": "86360C4FB06A7E5248EBE0B9C9015D852BFB292EEC98C3CEF0F01A87CE8B2E25"},
    {"uid": "8312923346", "password": "3B6574439556E9A6800FF323375A590D1F2B1B7A5BE61B8B6D30C25ED79478C1"},
    {"uid": "8312961041", "password": "B372069823BAA980548F3B64B0541CCA5FACC3EDEC0CF7EC6F53939CCE9EDB71"},
    {"uid": "8313057570", "password": "1B766BA96BB7D76E56CB6BBE82BD2F1EA4EE9542751F9764D61C9A39E6BBE281"}
]
BOT_RUNNING = False

def get_proto_field(d, key, default=None):
    if not d or not isinstance(d, dict): return default
    if key in d: v = d[key].get('data'); return v if v is not None else default
    if str(key) in d: v = d[str(key)].get('data'); return v if v is not None else default
    return default

def _decode_proto_manual(data):
    result = {}; offset = 0; data_len = len(data)
    while offset < data_len:
        header = 0; shift = 0
        while offset < data_len:
            b = data[offset]; offset += 1; header |= (b & 0x7F) << shift
            if not (b & 0x80): break
            shift += 7
            if shift > 28: break
        if header == 0: break
        fn = header >> 3; wt = header & 0x7
        if fn == 0: break
        if wt == 0:
            v = 0; shift = 0
            while offset < data_len:
                b = data[offset]; offset += 1; v |= (b & 0x7F) << shift
                if not (b & 0x80): break
                shift += 7
                if shift > 63: break
            result[fn] = v
        elif wt == 2:
            length = 0; shift = 0
            while offset < data_len:
                b = data[offset]; offset += 1; length |= (b & 0x7F) << shift
                if not (b & 0x80): break
                shift += 7
                if shift > 28: break
            if length > data_len - offset: break
            value = data[offset:offset+length]; offset += length
            try:
                s = value.decode('utf-8')
                if len(s) < 4 and all(32 <= ord(c) < 127 for c in s): result[fn] = s
                else:
                    nested = _decode_proto_manual(value); result[fn] = nested if nested else value.hex()
            except UnicodeDecodeError:
                nested = _decode_proto_manual(value); result[fn] = nested if nested else value.hex()
        elif wt == 5: offset += 4
        elif wt == 1: offset += 8
        else: break
    return result

def _wrap_manual(inner):
    try:
        alt = _decode_proto_manual(inner)
        if alt and len(alt) > 0: return {str(k): {"data": v} for k, v in alt.items()}
    except Exception: pass
    return None

def decode_protobuf_dict_safe(data):
    try: return {str(k): {"data": v} for k, v in _decode_proto_manual(data).items()}
    except Exception: return {}

async def decode_protobuf(data):
    try: return json.dumps({str(k): {"data": v} for k, v in _decode_proto_manual(data).items()})
    except Exception: return "{}"

class SquadMatchSync:
    def __init__(self):
        self.lock = asyncio.Lock(); self.active_squad_uids = set(); self.dead_squad_uids = set(); self.all_dead_event = asyncio.Event()
    async def reset_match(self, uids):
        async with self.lock: self.active_squad_uids = set(str(u) for u in uids); self.dead_squad_uids.clear(); self.all_dead_event.clear()
    async def mark_bot_dead(self, uid):
        async with self.lock:
            uid = str(uid)
            if uid in self.active_squad_uids:
                self.dead_squad_uids.add(uid)
                if len(self.dead_squad_uids) >= len(self.active_squad_uids): self.all_dead_event.set()
    async def wait_for_all_dead(self, timeout=360.0):
        try: await asyncio.wait_for(self.all_dead_event.wait(), timeout=timeout)
        except asyncio.TimeoutError: pass
squad_sync = SquadMatchSync()

def bypass_jitter(base, spread=0.35): return max(0.05, base + random.uniform(-spread, spread))
def bypass_packet_jitter(base, spread_ratio=0.35): return max(0.1, base + random.uniform(-base * spread_ratio, base * spread_ratio))
def bypass_hello_delay(): return random.uniform(0.05, 0.45)
def bypass_human_reconnect_delay(attempt): return max(0.05, min(attempt * 0.5, 2.0) + random.uniform(-0.4, 0.7))

def get_device_for_account(account_identifier):
    devices = {}
    if os.path.exists(DEVICES_FILE):
        try:
            with open(DEVICES_FILE, "r", encoding="utf-8") as f: devices = json.load(f)
        except Exception: pass
    key = str(account_identifier)
    if key in devices: return devices[key]
    dev = {"unique_device_id": f"Google|{uuid.uuid4()}", "brand": "Samsung", "model": "SM-G998B", "gpu_renderer": "Adreno (TM) 660", "system_software": "Android OS 12 / API-31", "screen_width": 1080, "screen_height": 2400, "screen_dpi": "420", "memory": 8192, "processor_details": "ARM64 FP ASIMD AES | 2800 | 8", "client_ip": f"{random.randint(103, 223)}.{random.randint(10, 250)}.{random.randint(10, 250)}.{random.randint(10, 250)}"}
    devices[key] = dev
    try:
        with open(DEVICES_FILE, "w", encoding="utf-8") as f: json.dump(devices, f, indent=2)
    except Exception: pass
    return dev

_DNS_CACHE = {}
async def resolve_host_cloudflare(hostname):
    if not hostname: return hostname
    parts = hostname.split('.')
    if len(parts) == 4 and all(p.isdigit() for p in parts): return hostname
    now = time.time()
    if hostname in _DNS_CACHE:
        ip, exp = _DNS_CACHE[hostname]
        if now < exp: return ip
    try:
        loop = asyncio.get_running_loop(); info = await loop.getaddrinfo(hostname, None, family=socket.AF_INET)
        if info: ip = info[0][4][0]; _DNS_CACHE[hostname] = (ip, now + 300); return ip
    except Exception: pass
    return hostname

def optimize_tcp_socket(sock):
    try: sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1); sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    except Exception: pass
def optimize_udp_socket(sock):
    try: sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 131072); sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 131072)
    except Exception: pass

client = httpx.AsyncClient(verify=False, timeout=15.0, limits=httpx.Limits(max_connections=100, max_keepalive_connections=50))
headers = {'User-Agent': 'UnityPlayer/2018.4.12f1', 'Connection': 'Keep-Alive', 'Accept-Encoding': 'gzip', 'Content-Type': 'application/x-www-form-urlencoded', 'X-Unity-Version': '2018.4.12f1', 'X-GA-SV': '1789535859', 'X-GA': 'v1 1', 'ReleaseVersion': 'OB55'}
AES_KEY = b'Yg&tc%DEuh6%Zc^8'; AES_IV = b'6oyZDr22E3ychjM%'

async def aes_encrypt(payload, key, iv): return AES.new(key, AES.MODE_CBC, iv).encrypt(pad(payload, AES.block_size))

async def version_config():
    url = f"https://version.ggwhitehawk.com/live/ver.php?version={FALLBACK_CLIENT_VERSION}&lang=hi&device=android&channel=android&appstore=googleplay&region=IND&whitelist_version=1.3.0&whitelist_sp_version=1.0.0"
    try:
        r = await client.get(url); r.raise_for_status(); d = r.json(); su, rv, lr = d.get("server_url"), d.get("remote_version"), d.get("latest_release_version")
        if su and rv and lr: return lr, rv, su
    except Exception: pass
    return None

async def get_access_token(uid, password):
    url = "https://100067.connect.garena.com/oauth/guest/token/grant"
    hdrs = {"Host": "100067.connect.garena.com", "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12; SM-G998B)", "Content-Type": "application/x-www-form-urlencoded", "Connection": "keep-alive"}
    data = {"uid": uid, "password": password, "response_type": "token", "client_type": "2", "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3", "client_id": "100067"}
    import socket as _s; _orig_gai = _s.getaddrinfo
    for attempt in range(5):
        try:
            def _patched_gai(host, port, *a, **kw):
                kw.pop("family", None)
                if host in ("100067.connect.garena.com", "100067.in.connect.garena.com"): return [(_s.AF_INET, _s.SOCK_STREAM, 6, '', ('43.205.19.48', port or 443))]
                return _orig_gai(host, port, *a, **kw)
            _s.getaddrinfo = _patched_gai
            async with httpx.AsyncClient(verify=False, timeout=25.0) as c2: r = await c2.post(url, headers=hdrs, data=data)
            if r.status_code == 200:
                d = r.json(); oid, at, pf = d.get("open_id"), d.get("access_token"), d.get("platform", 4)
                if oid and at: return oid, at, pf
        except Exception: pass
        finally: _s.getaddrinfo = _orig_gai
        await asyncio.sleep(1.5)
    return None

def encode_varint(n):
    if n < 0: return b''
    out = bytearray()
    while True:
        b = n & 0x7F; n >>= 7
        if n: b |= 0x80
        out.append(b)
        if not n: break
    return bytes(out)

def build_proto(fields):
    parts = []
    for k, v in fields.items():
        if isinstance(v, dict): nested = build_proto(v); parts.append(encode_varint((k << 3) | 2) + encode_varint(len(nested)) + nested)
        elif isinstance(v, int): parts.append(encode_varint((k << 3) | 0) + encode_varint(v))
        elif isinstance(v, (str, bytes)): ev = v.encode() if isinstance(v, str) else v; parts.append(encode_varint((k << 3) | 2) + encode_varint(len(ev)) + ev)
    return b''.join(parts)
def encrypt_api_bytes(plain_bytes): return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(plain_bytes, AES.block_size))
def _pb_varint(fn, val): return encode_varint((fn << 3) | 0) + encode_varint(val)
def _pb_length(fn, val):
    enc = val.encode('utf-8') if isinstance(val, str) else val
    return encode_varint((fn << 3) | 2) + encode_varint(len(enc)) + enc

def create_proto(fields):
    packet = bytearray()
    for field, value in fields.items():
        if isinstance(field, str): field = int(field)
        if isinstance(value, dict): packet.extend(_pb_length(field, bytes(create_proto(value))))
        elif isinstance(value, bool): packet.extend(_pb_varint(field, 1 if value else 0))
        elif isinstance(value, int): packet.extend(_pb_varint(field, value))
        elif isinstance(value, str): packet.extend(_pb_length(field, value))
        elif isinstance(value, (bytes, bytearray)): packet.extend(_pb_length(field, bytes(value)))
    return bytes(packet)

def create_packet(Pk, N, K, V):
    if isinstance(K, str): K = bytes.fromhex(K) if len(K) == 32 else K.encode()
    if isinstance(V, str): V = bytes.fromhex(V) if len(V) == 32 else V.encode()
    PkEnc = AES.new(K, AES.MODE_CBC, V).encrypt(pad(bytes.fromhex(Pk), 16)).hex()
    L = len(PkEnc) // 2; hexlen = hex(L)[2:]
    if len(hexlen) % 2 != 0: hexlen = '0' + hexlen
    pad_len = 12 - len(N) - len(hexlen)
    if pad_len < 0: pad_len = 0
    return bytes.fromhex(N + ('0' * pad_len) + hexlen + PkEnc)

def create_team(key, iv, game_version=FALLBACK_CLIENT_VERSION):
    fields = {
        1: 1, 
        2: {
            2: bytes.fromhex("01"), 3: 1, 4: 3, 5: "en", 
            8: {1: "IDC3", 2: 123, 3: "IND"}, 9: 1, 
            10: bytes.fromhex("01090a0b1219202729"), 11: 2, 13: 1,
            14: {1: "08FBA33B4BABE2790205390333330000009700050092005F72697EB2134DCBB2467625142201040e38e848dc0e748c3f6aa04d81000000ff1113090dcacfa16d", 2: 478, 3: "7e585d55", 4: "y[Z]", 6: 12, 7: "15686677735a7506101c", 8: str(game_version), 9: 3, 10: 1, 11: "03626253513637754174"},
            19: 329, 21: bytes.fromhex("374f521955"), 24: {1: 21},
            27: "a_6534489873065906362"
        }
    }
    return create_packet(create_proto(fields).hex(), "0515", key, iv)

def team_fresh(account_id, key, iv): return create_packet(create_proto({1: 72, 2: {1: int(account_id)}}).hex(), "0515", key, iv)
def invite_player_in_team(target_uid, key, iv, region="IND"): return create_packet(create_proto({1: 2, 2: {1: int(target_uid), 2: region, 4: 1}}).hex(), "0515", key, iv)
def accept_team_invite(target_uid, group_id, key, iv):
    fields = {1: 4, 2: {1: int(target_uid), 3: int(target_uid), 4: bytes.fromhex("0107090a0b120f19202729"), 8: 1, 9: {1: "08FBA33B0522052002041B0222220007000C00010004000547E265AE1080779546762514110104076fa2e8770e748c3f6a68ed75000000ff08080500cacfa16d", 2: 235, 3: {14: 80, 11: 86}, 4: "{Y\\R", 6: 13, 7: {2: 4}, 8: FALLBACK_CLIENT_VERSION, 9: 2, 10: 1, 11: "0362625351"}, 10: str(group_id), 11: {"1": "IDC3", "2": 107, "3": "IND"}, 13: "en", 16: "374f5219", 20: {1: 21}, 23: "a_6534489873065906362", 24: "https://dl-sg-production.freefiremobile.com/", 27: {1: 2, 2: 4}}
    return create_packet(create_proto(fields).hex(), "0515", key, iv)
def start_match_team(account_id, key, iv, region="IND"): return create_packet(create_proto({1: 9, 2: {1: int(account_id), 7: {1: "IDC3", 2: 410, 3: region}}}).hex(), "0515", key, iv)
def ready_for_game(uid, key, iv): return create_packet(create_proto({1: 15, 2: {1: uid, 2: 1}}).hex(), "0519", key, iv)
def guild_apply(guild_id, key, iv): return create_packet(create_proto({1: 20, 2: {1: int(guild_id), 2: 1, 3: 1}}).hex(), "0515", key, iv)

async def build_majorlogin_payload(open_id, access_token, platform, client_version, dev):
    p = {3: str(datetime.now())[:-7], 4: "free fire", 5: "1", 7: str(client_version), 8: str(dev.get("system_software")), 9: "Handheld", 10: "Telkomsel", 11: "CarrierDataNetwork", 12: str(dev.get("screen_width")), 13: str(dev.get("screen_height")), 14: str(dev.get("screen_dpi")), 15: str(dev.get("processor_details")), 16: str(dev.get("memory")), 17: str(dev.get("gpu_renderer")), 18: "OpenGL ES 3.2 v1.r49p1-03bet0", 19: str(dev.get("unique_device_id")), 20: str(dev.get("client_ip")), 21: "en", 22: str(open_id), 23: str(platform), 24: "Handheld", 25: str(dev.get("model")), 26: "IND", 29: str(access_token), 30: "1", 41: "Telkomsel", 42: "4G", 57: "7428b253defc164018c604a1ebbfebdf", 60: "109278", 61: "55402", 62: "868", 64: "55927", 65: "109278", 66: "55927", 67: "109278", 73: 2, 74: "/data/app/~~6Cw028g_ld-8Z0z2qhrOLA==/com.dts.freefireth-i3wiaEmpx8CbiRVhUMx_ag==/lib/arm64", 76: 1, 77: "b8e0cd5e295eee42f5860d3c86e483dd|/data/app/~~6Cw028g_ld-8Z0z2qhrOLA==/com.dts.freefireth-i3wiaEmpx8CbiRVhUMx_ag==/base.apk", 78: 6, 79: 1, 81: "32", 83: FALLBACK_CLIENT_VERSION_CODE, 85: 3, 86: "OpenGLES2", 87: 3071, 88: 4, 89: 14466, 93: "3rd_party", 94: "KqsHTyb7yHjsAiyNWUUZa0DSOD6U0AhDQ76smAo1WeHHHpSmJ8KMRyRrxb2ttgJqO9YOqO/K6AORAvDMAX/qBS8+JahIkrM7kHfzlfULbgRAoZ9r", 95: "111207", 96: "{\"cur_rate\":[60,90,120],\"support_etc2\":true}", 97: "1", 98: "1", 99: str(platform), 100: str(platform), 103: "1", 104: "52837", 105: "1", 106: "https://dl.gmc.freefiremobile.com/live/ABHotUpdates/|211c933168f55902c7dfbfd8c4e2957d", 107: "1.3fb8adbf45f44ce9"}
    return encrypt_api_bytes(build_proto(p))

class _MajorLoginRes:
    def __init__(self, **kw): self.account_id = kw.get('account_id', 0); self.region = kw.get('region', ''); self.token = kw.get('token', ''); self.url = kw.get('url', ''); self.server_time = kw.get('server_time', 0); self.aes_ak = kw.get('aes_ak', b''); self.iv_i = kw.get('iv_i', b'')
class _GetLoginDataRes:
    def __init__(self, **kw): self.nickname = kw.get('nickname', ''); self.functional_addrs = kw.get('functional_addrs', ''); self.informational_addrs = kw.get('informational_addrs', '')

def _parse_majorlogin_res(content):
    try:
        d = _decode_proto_manual(content)
        acc, reg, tok, url, stime = d.get(1) or 0, d.get(2) or '', d.get(8) or '', d.get(10) or '', d.get(21) or 0
        aes_ak_raw, iv_i_raw = d.get(22) or b'', d.get(23) or b''
        def _b(v):
            if isinstance(v, bytes): return v
            if isinstance(v, str):
                try: return bytes.fromhex(v)
                except Exception: return v.encode(errors='ignore')
            return b''
        aes_ak, iv_i = _b(aes_ak_raw), _b(iv_i_raw)
        if (not aes_ak or len(aes_ak) != 16) or (not iv_i or len(iv_i) != 16):
            cand_16 = []; off2 = 0; n2 = len(content)
            while off2 < n2:
                hdr = 0; shift = 0
                while off2 < n2:
                    b = content[off2]; off2 += 1; hdr |= (b & 0x7F) << shift
                    if not (b & 0x80): break
                    shift += 7
                    if shift > 28: break
                if hdr == 0: break
                fn, wt = hdr >> 3, hdr & 0x7
                if wt == 0:
                    while off2 < n2:
                        b = content[off2]; off2 += 1
                        if not (b & 0x80): break
                elif wt == 2:
                    ln = 0; shift = 0
                    while off2 < n2:
                        b = content[off2]; off2 += 1; ln |= (b & 0x7F) << shift
                        if not (b & 0x80): break
                        shift += 7
                        if shift > 28: break
                    if ln > n2 - off2: break
                    val = content[off2:off2+ln]; off2 += ln
                    if ln == 16: cand_16.append((fn, val))
                else: break
            if len(cand_16) >= 2:
                if not aes_ak or len(aes_ak) != 16: aes_ak = cand_16[-2][1]
                if not iv_i or len(iv_i) != 16: iv_i = cand_16[-1][1]
        if not tok or not aes_ak or len(aes_ak) != 16 or not iv_i or len(iv_i) != 16: return None
        return _MajorLoginRes(account_id=int(acc), region=reg, token=tok, url=url, server_time=int(stime), aes_ak=aes_ak, iv_i=iv_i)
    except Exception: return None

def _parse_getlogindata_res(content):
    try:
        d = _decode_proto_manual(content); nick, fa, ia = d.get(4) or '', d.get(14) or '', d.get(32) or ''
        if isinstance(nick, dict): nick = ''
        return _GetLoginDataRes(nickname=str(nick), functional_addrs=str(fa), informational_addrs=str(ia))
    except Exception: return None

async def send_majorlogin(data, release_version, server_url):
    try:
        url = f"{server_url}MajorLogin" if server_url.endswith('/') else f"{server_url}/MajorLogin"
        hdrs = headers.copy(); hdrs["ReleaseVersion"] = str(release_version)
        r = await client.post(url, headers=hdrs, data=data)
        if r.status_code == 200:
            c = r.content
            for off in [0, 4, 8, 16, 32, 64] + list(range(2, 128, 2)):
                m = _parse_majorlogin_res(c[off:])
                if m and m.region and m.token: return m
    except Exception: pass
    return None

async def send_getlogin(data, base_url, token, release_version):
    try:
        url = f"{base_url.rstrip('/')}/GetLoginData"
        hdrs = headers.copy(); hdrs["ReleaseVersion"] = release_version; hdrs['Authorization'] = f"Bearer {token}"; hdrs['Host'] = "clientbp.ppmainecoonghj.com"
        r = await client.post(url, headers=hdrs, data=data)
        if r.status_code == 200:
            c = r.content; rp = _parse_getlogindata_res(c)
            if not rp or not (rp.functional_addrs or rp.informational_addrs):
                for off in range(0, min(128, len(c))):
                    cand = _parse_getlogindata_res(c[off:])
                    if cand and (cand.functional_addrs or cand.informational_addrs): rp = cand; break
            if not rp: rp = _GetLoginDataRes()
            return rp, {str(k): {"data": v} for k, v in _decode_proto_manual(c).items()}
    except Exception: pass
    return None

async def build_tcp_startup_packet(account_id, token, server_time, key, iv, region="IND", typ='OnLine'):
    uid_hex, ts_hex = f"{int(account_id):016x}", f"{int(server_time):08x}"; enc = (await aes_encrypt(token.encode(), key, iv)).hex(); enc_len = f"{len(enc)//2:08x}"; reg = str(region).upper()
    return f"{'7114' if reg=='IND' else '7119'}{uid_hex}{ts_hex}00000000{enc_len}{enc}" if typ == 'OnLine' else f"{'9214' if reg=='IND' else '9219'}{uid_hex}{ts_hex}{enc_len}{enc}"
async def send_keep_alive(region="IND"): return bytes.fromhex("0214" if str(region).upper() == "IND" else "0219")

CRC7_TABLE = bytes([0,9,18,27,36,45,54,63,72,65,90,83,108,101,126,119,25,16,11,2,61,52,47,38,81,88,67,74,117,124,103,110,50,59,32,41,22,31,4,13,122,115,104,97,94,87,76,69,43,34,57,48,15,6,29,20,99,106,113,120,71,78,85,92,100,109,118,127,64,73,82,91,44,37,62,55,8,1,26,19,125,116,111,102,89,80,75,66,53,60,39,46,17,24,3,10,86,95,68,77,114,123,96,105,30,23,12,5,58,51,40,33,79,70,93,84,107,98,121,112,7,14,21,28,35,42,49,56,65,72,83,90,101,108,119,126,9,0,27,18,45,36,63,54,88,81,74,67,124,117,110,103,16,25,2,11,52,61,38,47,115,122,97,104,87,94,69,76,59,50,41,32,31,22,13,4,106,99,120,113,78,71,92,85,34,43,48,57,6,15,20,29,37,44,55,62,1,8,19,26,109,100,127,118,73,64,91,82,60,53,46,39,24,17,10,3,116,125,102,111,80,89,66,75,23,30,5,12,51,58,33,40,95,86,77,68,123,114,105,96,14,7,28,21,42,35,56,49,70,79,84,93,98,107,112,121])
_DELTA, _ROUNDS, _FIELD_SIZES, _FIELD_NAMES = 0x9E3779B9, 16, {0:1, 1:2, 2:2, 3:1, 4:2}, {0:"sendOption", 1:"cmd", 2:"orderId", 3:"flags", 4:"length"}

async def has_ssan_zig(n):
    z = (n << 1) & 0xFFFFFFFFFFFFFFFF; out = bytearray()
    while z >= 0x80: out.append((z & 0x7F) | 0x80); z >>= 7
    out.append(z); return bytes(out)
async def uleb_encode(n):
    out = bytearray()
    while True:
        b = n & 0x7F; n >>= 7
        if n: b |= 0x80
        out.append(b)
        if not n: break
    return bytes(out)
async def zigzag_encode_signed(n):
    try: n = int(n)
    except Exception: n = 0
    zz = (n << 1) ^ (n >> 63)
    if zz < 0: zz = -zz
    out = bytearray()
    while True:
        b = zz & 0x7F; zz >>= 7
        if zz: b |= 0x80
        out.append(b)
        if not zz: break
    return bytes(out)
async def tea_enc(v0, v1, k0, k1, k2, k3):
    s = 0
    for _ in range(_ROUNDS):
        s = (s + _DELTA) & 0xFFFFFFFF; v0 = (v0 + (((((v1<<4)&0xFFFFFFFF)+k0)&0xFFFFFFFF ^ ((v1+s)&0xFFFFFFFF) ^ (((v1>>5)+k1)&0xFFFFFFFF)))) & 0xFFFFFFFF; v1 = (v1 + (((((v0<<4)&0xFFFFFFFF)+k2)&0xFFFFFFFF ^ ((v0+s)&0xFFFFFFFF) ^ (((v0>>5)+k3)&0xFFFFFFFF)))) & 0xFFFFFFFF
    return v0, v1
async def tea_dec(v0, v1, k0, k1, k2, k3):
    s = (_DELTA * _ROUNDS) & 0xFFFFFFFF
    for _ in range(_ROUNDS):
        v1 = (v1 - (((((v0<<4)&0xFFFFFFFF)+k2)&0xFFFFFFFF ^ ((v0+s)&0xFFFFFFFF) ^ (((v0>>5)+k3)&0xFFFFFFFF)))) & 0xFFFFFFFF; v0 = (v0 - (((((v1<<4)&0xFFFFFFFF)+k0)&0xFFFFFFFF ^ ((v1+s)&0xFFFFFFFF) ^ (((v1>>5)+k1)&0xFFFFFFFF)))) & 0xFFFFFFFF; s = (s - _DELTA) & 0xFFFFFFFF
    return v0, v1
async def tea_cbc_encrypt(padded, key_bytes):
    k0,k1,k2,k3 = (struct.unpack_from("<I", key_bytes, o)[0] for o in (0,4,8,12)); out = bytearray(len(padded)); pc = bytearray(8); pi = bytearray(8)
    for i in range(0, len(padded), 8):
        x = bytearray(8)
        for j in range(8): x[j] = padded[i+j] ^ pc[j]
        e0,e1 = await tea_enc(struct.unpack_from("<I", x, 0)[0], struct.unpack_from("<I", x, 4)[0], k0,k1,k2,k3); enc = bytearray(8); struct.pack_into("<I", enc, 0, e0); struct.pack_into("<I", enc, 4, e1)
        for j in range(8): out[i+j] = enc[j] ^ pi[j]
        pc[:] = out[i:i+8]; pi[:] = x
    return bytes(out)
async def tea_cbc_decrypt(body, key_bytes):
    k0,k1,k2,k3 = (struct.unpack_from("<I", key_bytes, o)[0] for o in (0,4,8,12)); out = bytearray(len(body)); pi = bytearray(8); pc = bytearray(8); x = bytearray(8); dec = bytearray(8)
    for i in range(0, len(body), 8):
        for j in range(8): x[j] = body[i+j] ^ pi[j]
        d0,d1 = await tea_dec(struct.unpack_from("<I", x, 0)[0], struct.unpack_from("<I", x, 4)[0], k0,k1,k2,k3); struct.pack_into("<I", dec, 0, d0); struct.pack_into("<I", dec, 4, d1)
        for j in range(8): out[i+j] = dec[j] ^ pc[j]
        pc[:] = body[i:i+8]; pi[:] = dec
    return bytes(out)
async def build_padded(content):
    pad_len = (8 - (len(content) + 10) % 8) % 8
    return bytes([pad_len, 0, 0]) + b"\x00" * pad_len + content + b"\x00" * 7
async def encode_header(layout, so, cmd, oid, flags, length, k, v80):
    out = bytearray()
    for code in layout:
        val = {0:so, 1:cmd, 2:oid, 3:flags, 4:length}[code]
        if _FIELD_SIZES[code] == 1: out.append((val & 0xFF) ^ k)
        else: v = ((val & 0xFFFF) ^ v80) & 0xFFFF; out.append(v & 0xFF); out.append((v >> 8) & 0xFF)
    return bytes(out)
async def crc7_buff(crc, buf):
    c = crc & 0x7F
    for b in buf: c = CRC7_TABLE[((2*(c & 0xFF)) ^ (b & 0xFF)) & 0xFF] & 0x7F
    return c & 0x7F
async def sv_frame(msg_key, layout, so, cmd, oid, flags, content, key, encrypted=True):
    k = key[0]; v80 = ((k << 8) | k) & 0xFFFF; body = await tea_cbc_encrypt(await build_padded(content), key) if encrypted else content; hdr = bytearray([msg_key, 0]) + await encode_header(layout, so, cmd, oid, flags, len(body), k, v80); pkt = bytearray(hdr + body); pkt[1] = await crc7_buff(0, bytes(pkt[2:])) & 0x7F; return bytes(pkt)
async def build_packet(msg_key, layout, so, cmd, oid, flags, content, key, encrypted=True):
    k = key[0]; v80 = ((k << 8) | k) & 0xFFFF; body = await tea_cbc_encrypt(await build_padded(content), key) if encrypted else content; hdr = bytearray([msg_key, 0])
    for code in layout:
        val = {0:so, 1:cmd, 2:oid, 3:flags, 4:len(body)}[code]
        if _FIELD_SIZES[code] == 1: hdr.append((val & 0xFF) ^ k)
        else: v = ((val & 0xFFFF) ^ v80) & 0xFFFF; hdr.append(v & 0xFF); hdr.append((v >> 8) & 0xFF)
    pkt = bytearray(hdr + body); pkt[1] = await crc7_buff(0, bytes(pkt[2:])) & 0x7F; return bytes(pkt)
async def layouts_from_mask(mask): ru = [int(c) for c in str(mask).strip()]; return ru, [c for c in ru if c != 2]
async def build_hello_packet(text, key, layout):
    data = text.encode("utf-8"); content = b"\x10\x00\x00\x00" + data + b"\x00" * (29 - 4 - len(data)); k = key[0] if key else 10; v80 = ((k << 8) | k) & 0xFFFF; layout = [int(c) for c in str(layout).strip()] if isinstance(layout, str) else list(layout); enc_body = await tea_cbc_encrypt(await build_padded(content), key); hdr = await encode_header(layout, 1, 1, 0, 1, len(enc_body), k, v80); pkt = bytearray([0x63, 0x00]) + hdr + enc_body; pkt[1] = await crc7_buff(0, pkt[2:]) & 0x7F; return bytes(pkt).hex()

# [Rest of the engine - matchmaking, movement, play_game, etc. - same as your Termux bot.py]

# ═══════════════════════════ TELEGRAM BOT ═══════════════════════════
tg_bot = TgBot(token=TG_TOKEN)
dp = Dispatcher()

admin_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="▶️ Start Bots"), KeyboardButton(text="⏹ Stop Bots")]],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    intro = (
        f"👑 **ERIS Level Up Bot**\n\n"
        f"Welcome {message.from_user.first_name}!\n\n"
        f"Ye bot **ERIS** ne banaya hai.\n"
        f"Yaha se aap apni Free Fire ID ka level up kar sakte hain.\n\n"
        f"🔹 /levelup - Apni ID add karein\n"
    )
    if message.from_user.id == ADMIN_ID:
        intro += "\n🔸 Admin Commands:\n/startbots\n/stopbots"
        await message.answer(intro, reply_markup=admin_kb)
    else:
        await message.answer(intro)

@dp.message(Command("levelup"))
async def cmd_levelup(message: types.Message, state: FSMContext):
    await message.answer("🔑 Kripya apni ID aur Password bhejein:\nFormat: `UID:Password`\n(Example: `123456789:Pass123`)")
    await state.set_state(Form.waiting_for_creds)

@dp.message(Form.waiting_for_creds)
async def process_creds(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if ":" not in text:
        await message.answer("❌ Galat format! `UID:Password` bhejein.")
        return
        
    uid, pwd = text.split(":", 1)
    await state.clear()
    
    await tg_bot.send_message(ADMIN_ID, f"📩 **New ID Received!**\nFrom: {message.from_user.first_name} (@{message.from_user.username})\nGame UID: `{uid}`\nPass: ||{pwd}||")
    await message.answer(f"✅ Aapki ID `{uid}` ERIS ke paas bhej di gayi hai.")

@dp.message(Command("startbots"))
@dp.message(F.text == "▶️ Start Bots")
async def admin_start_bots(message: types.Message):
    global BOT_RUNNING
    if message.from_user.id != ADMIN_ID: return
    if BOT_RUNNING: return await message.answer("⚠️ Bots already running.")
    
    BOT_RUNNING = True
    await message.answer("🚀 **ERIS Bots Started. Matchmaking shuru ho rahi hai...**")
    
    for acc in HARDCODED_ACCOUNTS:
        asyncio.create_task(account_loop_guest(acc['uid'], acc['password']))

@dp.message(Command("stopbots"))
@dp.message(F.text == "⏹ Stop Bots")
async def admin_stop_bots(message: types.Message):
    global BOT_RUNNING
    if message.from_user.id != ADMIN_ID: return
    BOT_RUNNING = False
    await message.answer("🛑 **ERIS Bots Stopped.**")

async def main():
    print("[ERIS] Starting...")
    asyncio.create_task(dp.start_polling(tg_bot))
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
