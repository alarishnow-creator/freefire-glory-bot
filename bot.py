# -*- coding: utf-8 -*-
# DEVELOPER: ERIS
import sys, asyncio, httpx, random, json, socket, struct, time, os, uuid, math, itertools
from datetime import datetime
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from aiogram import Bot as TgBot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ═══════════════════════════ CONFIG ═══════════════════════════
TG_TOKEN = "8244534907:AAEnRgFtBHUDtn_E8WOIMop0JpGLZnBbCig"
ADMIN_ID = 7424554376
BOT_RUNNING = False

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

HARDCODED_ACCOUNTS = [
    {"uid": "8289010389", "password": "86360C4FB06A7E5248EBE0B9C9015D852BFB292EEC98C3CEF0F01A87CE8B2E25"},
    {"uid": "8312923346", "password": "3B6574439556E9A6800FF323375A590D1F2B1B7A5BE61B8B6D30C25ED79478C1"},
    {"uid": "8312961041", "password": "B372069823BAA980548F3B64B0541CCA5FACC3EDEC0CF7EC6F53939CCE9EDB71"},
    {"uid": "8313057570", "password": "1B766BA96BB7D76E56CB6BBE82BD2F1EA4EE9542751F9764D61C9A39E6BBE281"}
]

class Colors: GREEN='\033[92m'; FAIL='\033[91m'; WARNING='\033[93m'; CYAN='\033[96m'; MAGENTA='\033[95m'; WHITE='\033[97m'; ENDC='\033[0m'
def print_colored(t, c=Colors.WHITE):
    try: print(f"{c}{t}{Colors.ENDC}", flush=True)
    except Exception: pass
def print_success(t): print_colored(f"[+] {t}", Colors.GREEN)
def print_error(t): print_colored(f"[-] {t}", Colors.FAIL)
def print_warning(t): print_colored(f"[!] {t}", Colors.WARNING)
def print_info(t): print_colored(f"[i] {t}", Colors.CYAN)

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
    fields = {1: 4, 2: {1: int(target_uid), 3: int(target_uid), 4: bytes.fromhex("0107090a0b120f19202729"), 8: 1, 9: {1: "08FBA33B0522052002041B0222220007000C00010004000547E265AE1080779546762514110104076fa2e8770e748c3f6a68ed75000000ff08080500cacfa16d", 2: 235, 3: {14: 80, 11: 86}, 4: "{Y\\R", 6: 13, 7: {2: 4}, 8: FALLBACK_CLIENT_VERSION, 9: 2, 10: 1, 11: "0362625351"}, 10: str(group_id), 11: {"1": "IDC3", "2": 107, "3": "IND"}, 13: "en", 16: "374f5219", 20: {1: 21}, 23: "a_6534489873065906362", 24: "https://dl-sg-production.freefiremobile.com/", 27: {1: 2, 2: 4}}}
    return create_packet(create_proto(fields).hex(), "0515", key, iv)    return create_packet(create_proto(fields).hex(), "0515", key, iv)
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

MESSAGE_ID_TO_NAME = {1: "UDP_HELLO", 2: "UDP_ACK", 3: "UDP_PING", 100: "RUDP_JOIN_MATCH", 101: "RUDP_PLAYER_JOIN", 102: "RUDP_PLAYER_QUIT", 103: "RUDP_MATCH_END", 104: "RUDP_START_FIRE", 105: "RUDP_STOP_FIRE", 106: "RUDP_TAKE_DAMAGE", 107: "RUDP_DEAD", 447: "RUDP_JOIN_MATCH_PREPARE", 448: "RUDP_JOIN_MATCH_POST", 2001: "UDP_PLAYER_STATE_SYNC"}
async def classify(frame):
    name = MESSAGE_ID_TO_NAME.get(frame["cmd"], f"UNKNOWN_{frame['cmd']}")
    return "HELLO" if name == "UDP_HELLO" else "ACK" if name == "UDP_ACK" else "PING" if name == "UDP_PING" else "JOIN_MATCH" if name == "RUDP_JOIN_MATCH" else name
async def reply_for(frame, key, mask, ack_key=0x68, ping_key=0x6D, hello_key=0x5B):
    _, nr = await layouts_from_mask(mask); typ = await classify(frame)
    if typ == "HELLO": return typ, await build_packet(ack_key, nr, 0, 2, None, 1, b"\x01\x00", key)
    if typ == "ACK": return typ, await build_packet(ack_key, nr, 0, 2, None, 1, frame["content"] or b"\x01\x00", key)
    if typ == "PING": return typ, await build_packet(ping_key, nr, 0, 3, None, 0, (frame["content"][:4] if len(frame["content"]) >= 4 else frame["content"]) + b"\x00\x00\x00", key, encrypted=False)
    if typ == "JOIN_MATCH": return typ, await build_packet(ack_key, nr, 0, 2, None, 1, b"\x02\x00", key)
    return typ, None
async def keepalive_ping(sock, ip, port, key_bytes, mask, stop_event):
    nr = (await layouts_from_mask(mask))[1]; ping_keys = [0x66, 0x6D, 0x69, 0x6C, 0x6B, 0x6E, 0x6F, 0x70]; loop = asyncio.get_event_loop(); i = 0
    while not stop_event.is_set():
        pk = ping_keys[i % len(ping_keys)]; counter = int(time.time() * 1000) & 0xFFFFFFFF; pkt = await build_packet(pk, nr, 0, 3, None, 0, struct.pack("<I", counter) + b"\x00\x00\x00", key_bytes, encrypted=False)
        try: await loop.sock_sendto(sock, pkt, (ip, port))
        except Exception: pass
        i += 1
        try: await asyncio.wait_for(stop_event.wait(), timeout=bypass_packet_jitter(3.0, 0.4))
        except asyncio.TimeoutError: pass
async def try_header(buf, layout, k, v80):
    off = 2; out = {}
    for code in layout:
        size = _FIELD_SIZES[code]
        if off + size > len(buf): return None
        out[_FIELD_NAMES[code]] = ((buf[off] ^ k) if size == 1 else ((buf[off] | (buf[off+1] << 8)) ^ v80) & 0xFFFF); off += size
    out["headerLen"] = off; return out
async def oicq_unpad(padded):
    if not padded or len(padded) < 8 or not all(padded[-1-i] == 0 for i in range(7)): return None
    pad_len = padded[0] & 0x07; s = 3 + pad_len; e = len(padded) - 7
    return padded[s:e] if s < e else b""
async def decode_packet(packet, key, mask=None):
    data = bytes(packet) if isinstance(packet, bytes) else bytes.fromhex(packet)
    if len(data) < 8: return None
    k = key[0]; v80 = ((k << 8) | k) & 0xFFFF; crc_ok = (data[1] & 0x7F) == await crc7_buff(0, data[2:]); candidates = []
    layouts = [("RUDP", list(p)) for p in itertools.permutations([0,1,2,3,4])] + [("nonRUDP", list(p)) for p in itertools.permutations([0,1,3,4])] if not mask else [("RUDP", (await layouts_from_mask(mask))[0]), ("nonRUDP", (await layouts_from_mask(mask))[1])]
    for kind, layout in layouts:
        f = await try_header(data, layout, k, v80)
        if not f or f["flags"] > 7 or f["sendOption"] > 7 or f["length"] != len(data) - f["headerLen"]: continue
        body = data[f["headerLen"]:f["headerLen"]+f["length"]]; content = None
        if f["flags"] & 1:
            if len(body) < 8 or len(body) % 8 != 0: continue
            content = await oicq_unpad(await tea_cbc_decrypt(body, key))
            if content is None: continue
        else: content = body
        candidates.append({"kind":kind, "layout":layout, "headerLen":f["headerLen"], "msgKey":data[0], "cmd":f["cmd"], "flags":f["flags"], "sendOption":f["sendOption"], "orderId":f.get("orderId"), "length":f["length"], "content":content, "crcOk":crc_ok, "score":(1 if crc_ok else 0) + (1 if content is not None else 0)})
    if not candidates: return None
    candidates.sort(key=lambda c: c["score"], reverse=True); return candidates[0]
async def build_match_startup_packets(token, udp_key, match_code, account_id, block_val, server_ip="", region="IND", client_version=FALLBACK_CLIENT_VERSION, client_version_code=FALLBACK_CLIENT_VERSION_CODE, access_token="", mode_id=1, map_id=1):
    token = token.strip(); udp_key = bytes.fromhex(udp_key); match_code = [int(ch) for ch in str(match_code).strip()]; thunder_jwt = token[:660] if len(token) > 660 else token; sharma_jwt = token[660:] if len(token) > 660 else ""; eth = thunder_jwt.encode() if isinstance(thunder_jwt, str) else thunder_jwt; esh = sharma_jwt.encode() if isinstance(sharma_jwt, str) else sharma_jwt; garena420 = await has_ssan_zig(len(eth)) + eth; reg = str(region).upper() if region else "IND"
    csoversea_block = bytes.fromhex("ca0163736f7665727365612e7374726f6e67686f6c642e66726565666972656d6f62696c652e636f6d3b302e302e302e303b33342e3132362e37362e34353b33342e38372e3137372e31343b33342e38372e3137302e3233303b33352e3138352e3138332e3537000000000000010000000000000000000000000100000800000100000000000100a8a2d7bebd8d8bdf110200")
    mid = bytes.fromhex('0000000001000102030101') + await has_ssan_zig(len(reg)) + reg.encode() + bytes.fromhex('0001030003000004') + await has_ssan_zig(len(client_version)) + client_version.encode() + await has_ssan_zig(len(client_version_code)) + client_version_code.encode() + csoversea_block + await has_ssan_zig(len(server_ip.split(':')[0] if server_ip else "0.0.0.0")) + (server_ip.split(':')[0] if server_ip else "0.0.0.0").encode()
    if access_token: mid += await has_ssan_zig(len(access_token.strip())) + access_token.strip().encode()
    mid += await has_ssan_zig(len(esh)) + esh; tg = await uleb_encode(int(account_id)) + await uleb_encode(int(block_val)) + await uleb_encode(1) + await uleb_encode(int(mode_id)) + await uleb_encode(int(block_val)) + await uleb_encode(int(map_id)) + mid
    return (await sv_frame(0x5E, match_code, 2, 447, 0, 1, garena420, udp_key)).hex(), (await sv_frame(0x5A, match_code, 2, 448, 1, 1, tg, udp_key)).hex()
async def build_movement_packet_2001(key_bytes, msg_key, player_state, x, y, z, tick, counter, move_state, account_uid, room_code, phase="game"):
    TAIL = b"\x00"*7 + b"\x93\xca\xd5\xf9\x0b" + b"\x8e\xfe\xfc\xf7\x0b" + b"\xf4\xe0\xfe\xf7\x03" + b"\x00\x00" if phase == "game" else b"\x00"*7 + b"\xbd\xb6\xe1\xf3\x03" + b"\x00" + b"\xc4\xb6\xe1\xfb\x0b" + b"\x00\x00"
    body = await uleb_encode(int(account_uid)) + await uleb_encode(int(player_state)) + await zigzag_encode_signed(int(x)) + await zigzag_encode_signed(int(y)) + await zigzag_encode_signed(int(z)) + b"\x00" + await uleb_encode(int(move_state)) + TAIL + await uleb_encode(int(tick)) + b"\x00\x00\x00" + await uleb_encode(int(counter))
    k = key_bytes[0]; v80 = ((k << 8) | k) & 0xFFFF; h = bytearray([msg_key & 0xFF, 0x00, 0x00 ^ k]) + ((2001 ^ v80) & 0xFFFF).to_bytes(2, "little") + ((len(body) ^ v80) & 0xFFFF).to_bytes(2, "little") + bytes([0x00 ^ k]); h[1] = (await crc7_buff(0, bytes(h[2:]) + body)) & 0x7F; return bytes(h) + body
class MovementTracker:
    PLAYER_STATE = {"idle":0, "walk":1, "run":2, "sprint":3, "jump":4, "crouch":5, "prone":6}
    def __init__(self): self.tick = 0; self.counter = 0; self.angle = random.uniform(0, 6.2832); self.speed_multiplier = 1.0; self.curr_x = random.randint(-400, 400); self.curr_y = 15; self.curr_z = random.randint(-400, 400); self.state = "run"
    def next(self):
        self.tick = (self.tick + 1) & 0xFFFFFFFF; self.counter = (self.counter + 1) & 0xFFFFFFFF; self.angle += random.uniform(0.1, 0.3); step = random.randint(120, 280) * self.speed_multiplier; self.curr_x += int(step * math.cos(self.angle)); self.curr_z += int(step * math.sin(self.angle)); return self.PLAYER_STATE.get(self.state, 2), self.curr_x, self.curr_y, self.curr_z, 0x0F, self.tick, self.counter, self.speed_multiplier, self.state
async def movement_worker(sock, ip, port, udp_key_bytes, match_code, account_id, stop_event, match_index):
    loop = asyncio.get_event_loop(); addr = (ip, port); tracker = MovementTracker(); sent = 0
    try:
        await asyncio.sleep(bypass_jitter(3.0, 0.5))
        while not stop_event.is_set():
            try:
                ps, x, y, z, ms, tick, cnt, sm, st = tracker.next(); pkt = await build_movement_packet_2001(udp_key_bytes, 0x6B, ps, x, y, z, tick, cnt, ms, account_id, match_code, phase="game"); await loop.sock_sendto(sock, pkt, addr); sent += 1; wait = bypass_packet_jitter(max(0.10, min(0.24 / max(0.7, min(float(sm), 1.6)), 0.40)), 0.20)
                try: await asyncio.wait_for(stop_event.wait(), timeout=wait); break
                except asyncio.TimeoutError: pass
            except Exception: await asyncio.sleep(0.5)
    except asyncio.CancelledError: pass
async def anti_afk_worker(sock, ip, port, udp_key_bytes, match_code, account_id, stop_event, match_index):
    addr = (ip, port); loop = asyncio.get_event_loop(); pid = int(account_id)
    try:
        await asyncio.sleep(bypass_jitter(2.5, 0.5))
        while not stop_event.is_set():
            try:
                ts = int(time.time() * 1000) & 0xFFFFFFFF; wid = random.choice([101, 102, 103, 201, 202]); fp = await build_packet(0x68, (await layouts_from_mask(match_code))[1], 0, 104, None, 0, struct.pack("<IIHB", pid & 0xFFFFFFFF, ts, wid, 1), udp_key_bytes, encrypted=False); await loop.sock_sendto(sock, fp, addr); await asyncio.sleep(bypass_jitter(random.uniform(0.15, 0.30), 0.05)); sp = await build_packet(0x68, (await layouts_from_mask(match_code))[1], 0, 105, None, 0, struct.pack("<IIHB", pid & 0xFFFFFFFF, ts + 200, wid, 0), udp_key_bytes, encrypted=False); await loop.sock_sendto(sock, sp, addr)
                try: await asyncio.wait_for(stop_event.wait(), timeout=bypass_packet_jitter(random.uniform(1.8, 3.5), 0.25)); break
                except asyncio.TimeoutError: pass
            except Exception: await asyncio.sleep(1.0)
    except asyncio.CancelledError: pass
async def play_game(server_ip_port, thunder, sharma, udp_key, match_code, account_id, player_region, client_version, key, iv, match_index, on_match_complete=None):
    t0 = time.time(); ping_task = anti_task = move_task = None; sock = None; uid_str = str(account_id); completed = False; ping_stop = asyncio.Event(); anti_stop = asyncio.Event(); move_stop = asyncio.Event()
    try:
        ip, port = server_ip_port.split(":"); port = int(port); rip = await resolve_host_cloudflare(ip); loop = asyncio.get_event_loop(); sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.bind(('0.0.0.0', 0)); optimize_udp_socket(sock); sock.setblocking(False); udp_key_bytes = bytes.fromhex(udp_key); await asyncio.sleep(bypass_hello_delay()); await loop.sock_sendto(sock, bytes.fromhex(await build_hello_packet(f"{account_id}_2585", udp_key_bytes, match_code)), (rip, port)); ack_state = "waiting_for_hello_reply"; thunder_sent = False; join_match_rcv = False; local_closed = False; send_lock = asyncio.Lock(); anti_started = False; ping_task = asyncio.create_task(keepalive_ping(sock, rip, port, udp_key_bytes, match_code, ping_stop)); last_activity = time.time()
        async def start_workers():
            nonlocal anti_task, move_task, anti_started
            if anti_started: return
            anti_started = True; anti_task = asyncio.create_task(anti_afk_worker(sock, rip, port, udp_key_bytes, match_code, account_id, anti_stop, match_index)); move_task = asyncio.create_task(movement_worker(sock, rip, port, udp_key_bytes, match_code, account_id, move_stop, match_index))
        async def send_startup():
            nonlocal ack_state, thunder_sent
            if thunder_sent: return
            async with send_lock:
                if thunder_sent: return
                await loop.sock_sendto(sock, bytes.fromhex(thunder), (rip, port)); thunder_sent = True; await asyncio.sleep(bypass_jitter(0.1, 0.05)); await loop.sock_sendto(sock, await build_packet(0x68, (await layouts_from_mask(match_code))[1], 0, 2, None, 1, b"\x01\x00", udp_key_bytes), (rip, port)); await asyncio.sleep(bypass_jitter(0.2, 0.05)); await loop.sock_sendto(sock, bytes.fromhex(sharma), (rip, port)); ack_state = "thunder_sharma_sent"; await start_workers()
        while not local_closed:
            if time.time() - t0 > MAX_MATCH_DURATION: break
            try:
                resp, saddr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), timeout=1.5)
                if resp:
                    last_activity = time.time(); frame = await decode_packet(resp, udp_key_bytes, match_code)
                    if frame:
                        pt = await classify(frame)
                        if frame['cmd'] == 107:
                            await squad_sync.mark_bot_dead(uid_str); wait_remaining = DEATH_WAIT_SECONDS
                            while wait_remaining > 0: await asyncio.sleep(2.0); wait_remaining -= 2.0
                            completed = True; local_closed = True; continue
                        if frame['cmd'] == 103:
                            wait_remaining = MATCH_END_WAIT_SECONDS
                            while wait_remaining > 0: await asyncio.sleep(2.0); wait_remaining -= 2.0
                            completed = True; await squad_sync.mark_bot_dead(uid_str); local_closed = True; continue
                        if frame['cmd'] == 101: await loop.sock_sendto(sock, await build_packet(0x68, (await layouts_from_mask(match_code))[1], 0, 2, None, 1, b"\x01\x00", udp_key_bytes), saddr); continue
                        if pt in ["ACK", "PING", "HELLO", "JOIN_MATCH"]:
                            if pt == "HELLO" and ack_state == "waiting_for_hello_reply": ack_state = "ack_sent_waiting"
                            elif pt == "ACK" and ack_state in ("waiting_for_hello_reply", "ack_sent_waiting"): ack_state = "ready_to_send_thunder"
                            _, r = await reply_for(frame, udp_key_bytes, match_code)
                            if r: await loop.sock_sendto(sock, r, saddr)
            except asyncio.TimeoutError:
                if ack_state == "ready_to_send_thunder" and not thunder_sent: await send_startup()
                elif ack_state == "waiting_for_hello_reply" and (time.time() - t0) > 25.0: await squad_sync.mark_bot_dead(uid_str); break
                elif ack_state == "thunder_sharma_sent" and (time.time() - last_activity) > MATCH_IDLE_TIMEOUT: completed = True; await squad_sync.mark_bot_dead(uid_str); break
                continue
            except Exception: await asyncio.sleep(0.5); continue
            if ack_state == "ready_to_send_thunder" and not thunder_sent:
                try: await send_startup()
                except Exception: pass
        await squad_sync.wait_for_all_dead(); return f"match #{match_index} finished"
    except Exception as e:
        try: await squad_sync.mark_bot_dead(uid_str)
        except Exception: pass
        return f"match #{match_index} error"
    finally:
        if completed and on_match_complete: asyncio.create_task(on_match_complete())
        anti_stop.set(); move_stop.set(); ping_stop.set()
        for t in (anti_task, move_task, ping_task):
            if t:
                try: await asyncio.wait_for(t, timeout=2.0)
                except Exception: t.cancel(); 
                try: await t
                except Exception: pass
        if sock: sock.close()
async def _process_social_packet(raw_bytes, account_data, tag="MAIN"):
    hex_data = raw_bytes.hex(); candidates = []
    for off in [5, 6, 10, 8, 12, 4, 0]:
        if off >= len(hex_data): continue
        try: inner = bytes.fromhex(hex_data[off:])
        except Exception: continue
        decoded = decode_protobuf_dict_safe(inner) or _wrap_manual(inner)
        if decoded: candidates.append((off, decoded))
    if not candidates: return
    candidates.sort(key=lambda x: len(x[1]) if isinstance(x[1], dict) else 0, reverse=True); best_off, decoded = candidates[0]
    def _v(c, k): v = c.get(k) if k in c else c.get(str(k)); return v["data"] if isinstance(v, dict) and "data" in v else v
    f5w = decoded.get("5") or decoded.get(5) if isinstance(decoded, dict) else None; f5 = f5w["data"] if isinstance(f5w, dict) and "data" in f5w else f5w; target = None
    if isinstance(f5, dict):
        for fk in [1, 2, 3, 4, 6]:
            c = _v(f5, fk)
            if c and str(c).isdigit() and 6 <= len(str(c)) <= 15: target = str(c); break
    if not target: return
    own = str(account_data.get('account_id', '')) if account_data else ''
    if own and target == own: return
    if not _accept_friend_request or not account_data: return
    jwt, srv, rel, own_id = account_data.get('token'), account_data.get('server_url'), account_data.get('release_version'), account_data.get('account_id')
    if not (jwt and srv and rel and own_id): return
    try:
        payload = bytes.fromhex(encrypt_api_bytes(create_proto({"1": int(target), "2": int(own_id)})).hex()); hdrs = {"authorization": f"Bearer {jwt}", "host": srv.replace("https://", "").replace("http://", "").split("/")[0], "x-ga": "v1 1", "content-type": "application/x-www-form-urlencoded", "accept-encoding": "deflate, gzip", "releaseversion": f"{rel}", "user-agent": "UnityPlayer/2022.3.47f1", "accept": "*/*", "x-unity-version": "2022.3.47f1"}
        async with httpx.AsyncClient(verify=False, timeout=8.0) as s:
            r = await s.post(f"{srv.rstrip('/')}/ConfirmFriendRequest", headers=hdrs, content=payload)
            if r.status_code == 200: print_success(f"[FRIEND-{tag}] {target}")
    except Exception: pass
async def _handle_team_invite(hex_data, pl, uid_str, current_account_data, current_key, current_iv, writer):
    candidates = []
    for off in [10, 8, 6, 12, 14, 4, 16, 0, 20, 2]:
        if off >= len(hex_data) or len(hex_data) - off < 4: continue
        try: inner = bytes.fromhex(hex_data[off:])
        except Exception: continue
        dec = decode_protobuf_dict_safe(inner) or _wrap_manual(inner)
        if dec: candidates.append((off, dec))
    if not candidates: return False
    candidates.sort(key=lambda x: len(x[1]) if isinstance(x[1], dict) else 0, reverse=True); best_off, dec = candidates[0]
    def _g(d, k): v = d.get(k) if k in d else d.get(str(k)); return v["data"] if isinstance(v, dict) and "data" in v else v
    group_id = next((str(c) for k in list(dec.keys()) if isinstance(c := _g(dec, k), str) and 20 <= len(c) <= 40), None)
    own_acc = str(current_account_data.get('account_id')) if current_account_data else None
    inviter = next((str(c) for k in list(dec.keys()) if (c := _g(dec, k)) and str(c).isdigit() and 6 <= len(str(c)) <= 15 and str(c) not in (uid_str, own_acc)), None)
    if inviter and group_id and _team_state["leader_uid"] != uid_str:
        async with _team_state["members_lock"]:
            if uid_str in _team_state["members"]: return True
        for attempt in range(3):
            try:
                if writer and not writer.is_closing(): writer.write(accept_team_invite(int(inviter), group_id, current_key, current_iv)); await writer.drain(); await _team_member_join(uid_str); return True
            except Exception: pass
            await asyncio.sleep(0.8)
    return False
_match_counters = {}; _match_counter_lock = asyncio.Lock()
async def _inc_match(uid):
    async with _match_counter_lock: _match_counters[uid] = _match_counters.get(uid, 0) + 1; return _match_counters[uid]
async def _dec_match(uid):
    async with _match_counter_lock:
        if uid in _match_counters and _match_counters[uid] > 0: _match_counters[uid] -= 1
        return _match_counters.get(uid, 0)
async def _get_match_count(uid):
    async with _match_counter_lock: return _match_counters.get(uid, 0)
_team_state = {"peers": {}, "leader_uid": None, "team_code": None, "pk_code": None, "members": set(), "members_lock": asyncio.Lock(), "lock": asyncio.Lock()}
async def _team_member_join(uid):
    async with _team_state["members_lock"]: _team_state["members"].add(str(uid))
async def _team_member_leave(uid):
    async with _team_state["members_lock"]: _team_state["members"].discard(str(uid))
async def _team_member_count():
    async with _team_state["members_lock"]: return len(_team_state["members"])
async def _team_member_reset():
    async with _team_state["members_lock"]: _team_state["members"].clear()
async def functional_battle_royale(addrs, starter_packet, account_region, client_version, key, iv, account_id="", account_data=None, account_level=2):
    ip, port = addrs.split(":"); play_matches = []; uid_str = str(account_id); current_token = starter_packet; current_key = key; current_iv = iv; current_account_data = account_data; reconnect_count_total = 0; _writer_ref = {"w": None}; _team_active = {"flag": True}
    async def trigger_post_match_refresh():
        await asyncio.sleep(EXP_REFRESH_AFTER_MATCH_DELAY)
        if uid_str in bot_state.account_credentials: await refresh_account_profile(bot_state.account_credentials[uid_str])
    async def force_guild_join_api():
        try:
            jwt, srv, rel, own_id = current_account_data.get('token'), current_account_data.get('server_url'), current_account_data.get('release_version'), current_account_data.get('account_id')
            payload = bytes.fromhex(encrypt_api_bytes(create_proto({"1": int(own_id), "2": 3055649830})).hex())
            async with httpx.AsyncClient(verify=False, timeout=8.0) as s:
                r = await s.post(f"{srv.rstrip('/')}/JoinGuild", headers={"authorization": f"Bearer {jwt}", "host": srv.replace("https://", "").replace("http://", "").split("/")[0], "content-type": "application/x-www-form-urlencoded", "releaseversion": f"{rel}", "user-agent": "UnityPlayer/2022.3.47f1"}, content=payload)
                if r.status_code == 200: print_success(f"[GUILD API] Joined Guild via API for {own_id}")
        except Exception: pass
    async def _guild_loop():
        try:
            while _team_active["flag"]:
                if _writer_ref["w"] and not _writer_ref["w"].is_closing():
                    await force_guild_join_api(); _g_pkt = guild_apply(GUILD_UID, current_key, current_iv)
                    try: _writer_ref["w"].write(_g_pkt); await _writer_ref["w"].drain(); print_success(f"[GUILD] Sent join for {uid_str}")
                    except Exception: pass
                await asyncio.sleep(GUILD_APPROVE_INTERVAL)
        except asyncio.CancelledError: raise
    async def _team_coordinator():
        try:
            while True:
                async with _team_state["lock"]: n = len(_team_state["peers"])
                if n >= TEAM_SIZE: break
                if bot_state.is_paused(uid_str): return
                await asyncio.sleep(0.5)
            async with _team_state["lock"]: is_leader = (_team_state["leader_uid"] == uid_str); peers_snapshot = dict(_team_state["peers"])
            if not is_leader: return
            await asyncio.sleep(TEAM_READY_DELAY); _team_member_reset(); own_id_num = current_account_data.get('account_id') or int(uid_str)
            _writer_ref["w"].write(create_team(current_key, current_iv, client_version)); await _writer_ref["w"].drain(); await _team_member_join(uid_str)
            await asyncio.sleep(6.0); peer_uids = [int(info["data"].get("account_id") or peer_uid) for peer_uid, info in peers_snapshot.items() if peer_uid != uid_str]
            heartbeat_stop = asyncio.Event()
            async def heartbeat_loop():
                while not heartbeat_stop.is_set():
                    try: _writer_ref["w"].write(team_fresh(int(own_id_num), current_key, current_iv)); await _writer_ref["w"].drain()
                    except Exception: pass
                    try: await asyncio.wait_for(heartbeat_stop.wait(), timeout=TEAM_HEARTBEAT_INTERVAL)
                    except asyncio.TimeoutError: pass
            hb_task = asyncio.create_task(heartbeat_loop()); invite_start = time.time()
            while time.time() - invite_start < TEAM_INVITE_MAX_TIME:
                if not _team_active["flag"] or bot_state.is_paused(uid_str) or await _team_member_count() >= TEAM_SIZE: break
                for tuid in peer_uids:
                    async with _team_state["members_lock"]:
                        if str(tuid) in _team_state["members"]: continue
                    try: _writer_ref["w"].write(invite_player_in_team(tuid, current_key, current_iv, region=account_region)); await _writer_ref["w"].drain()
                    except Exception: pass
                    await asyncio.sleep(0.5)
                try: await asyncio.wait_for(heartbeat_stop.wait(), timeout=TEAM_INVITE_CYCLE_WAIT)
                except asyncio.TimeoutError: pass
            if await _team_member_count() < TEAM_SIZE:
                heartbeat_stop.set()
                try: hb_task.cancel(); await hb_task
                except Exception: pass
                return
            await asyncio.sleep(TEAM_FINAL_WAIT); heartbeat_stop.set()
            try: hb_task.cancel(); await hb_task
            except Exception: pass
            while _team_active["flag"]:
                if bot_state.is_paused(uid_str): break
                async with _team_state["lock"]:
                    if _team_state["leader_uid"] != uid_str: break
                await asyncio.sleep(20.0); _writer_ref["w"].write(ready_for_game(int(own_id_num), current_key, current_iv)); await _writer_ref["w"].drain(); await asyncio.sleep(1.0); _writer_ref["w"].write(start_match_team(int(own_id_num), current_key, current_iv, region=account_region)); await _writer_ref["w"].drain()
                try: await asyncio.wait_for(asyncio.sleep(5.0), timeout=5.5)
                except asyncio.TimeoutError: pass
        except asyncio.CancelledError: raise
    async def _member_match_trigger():
        try:
            await asyncio.sleep(TEAM_READY_DELAY + TEAM_MEMBER_START_DELAY)
            async with _team_state["lock"]:
                if _team_state["leader_uid"] == uid_str: return
            while True:
                if bot_state.is_paused(uid_str): break
                if _writer_ref["w"] and not _writer_ref["w"].is_closing():
                    _writer_ref["w"].write(ready_for_game(int(current_account_data.get('account_id')), current_key, current_iv)); await _writer_ref["w"].drain(); await asyncio.sleep(1.0); sm = start_match_team(int(current_account_data.get('account_id')), current_key, current_iv, region=account_region); _writer_ref["w"].write(sm); await _writer_ref["w"].drain()
                try: await asyncio.wait_for(asyncio.sleep(5.0), timeout=5.5)
                except asyncio.TimeoutError: pass
        except asyncio.CancelledError: raise
    try:
        while True:
            writer = None; gateway_ping_task = None; team_coord_task = None; member_trigger_task = None; guild_task = None
            try:
                if current_account_data:
                    fresh = cache_get(str(current_account_data['auth_uid'])) if current_account_data.get('auth_type') == 'guest' else cache_get(f"tok_{current_account_data.get('auth_token')[:20]}")
                    if fresh:
                        current_account_data = fresh; current_key = fresh['aes_ak']; current_iv = fresh['iv_i']; current_token = await build_tcp_startup_packet(fresh['account_id'], fresh['token'], fresh['server_time'], current_key, current_iv, region=fresh.get('region', account_region), typ='OnLine')
                    else: cache_invalidate(str(current_account_data.get('auth_uid'))); raise ConnectionError("Cache expired")
                rip = await resolve_host_cloudflare(ip); reader, writer = await asyncio.open_connection(rip, int(port)); _writer_ref["w"] = writer
                if raw_sock := writer.get_extra_info('socket'): optimize_tcp_socket(raw_sock)
                await asyncio.sleep(bypass_hello_delay()); writer.write(bytes.fromhex(current_token)); await writer.drain()
                async def func_gateway_keepalive():
                    ka_bytes = await send_keep_alive(account_region)
                    while True:
                        await asyncio.sleep(2.0)
                        try:
                            if writer and not writer.is_closing(): writer.write(ka_bytes); await writer.drain()
                        except Exception: break
                gateway_ping_task = asyncio.create_task(func_gateway_keepalive()); connection_start_time = asyncio.get_running_loop().time(); last_watchdog_check = connection_start_time
                async with _team_state["lock"]:
                    _team_state["peers"][uid_str] = {"writer": writer, "data": current_account_data, "key": current_key, "iv": current_iv}
                    if _team_state["leader_uid"] is None: _team_state["leader_uid"] = uid_str
                if TEAM_MODE:
                    team_coord_task = asyncio.create_task(_team_coordinator())
                    member_trigger_task = asyncio.create_task(_member_match_trigger())
                    guild_task = asyncio.create_task(_guild_loop())
                no_response_count = 0
                while True:
                    play_matches[:] = [m for m in play_matches if not m.done()]; active = await _get_match_count(uid_str)
                    try: bot_state.update_status(uid_str, "ONLINE" if active == 0 else "IN_MATCH", active)
                    except Exception: pass
                    now = asyncio.get_running_loop().time()
                    if now - last_watchdog_check >= MATCH_WATCHDOG_CHECK:
                        last_watchdog_check = now
                        if (now - connection_start_time) > MATCH_SEARCH_TIMEOUT: raise ConnectionError("Search watchdog")
                    try: data = await asyncio.wait_for(reader.read(8192), timeout=0.5)
                    except asyncio.TimeoutError:
                        no_response_count += 1
                        if no_response_count > TEAM_IDLE_ITERS_TEAM: raise ConnectionError("Idle")
                        continue
                    if not data: raise ConnectionError("closed")
                    hex_data = data.hex(); pl = len(data); no_response_count = 0
                    if hex_data.startswith("0600") and pl > 20: await _process_social_packet(data, current_account_data, tag="MAIN"); continue
                    if hex_data.startswith("05") and pl > 10: await _handle_team_invite(hex_data, pl, uid_str, current_account_data, current_key, current_iv, writer); continue
                    if hex_data.startswith("0300") and pl >= 300:
                        print_colored("=" * 60, Colors.GREEN); print_colored("MATCH FOUND! Loading...", Colors.GREEN); print_colored("=" * 60, Colors.GREEN)
                        for tk in (team_coord_task, member_trigger_task, guild_task):
                            if tk and not tk.done(): tk.cancel()
                        _team_active["flag"] = False
                        try:
                            res = json.loads(await decode_protobuf(data[10:])); def _saf(v): return v.get('data') if isinstance(v, dict) else v
                            token = udp_key = match_code = server_ip_port = match_account_id = block_val = None
                            if '42' in res: match_code = _saf(res['42'])
                            if isinstance(_saf(res.get('5')), dict):
                                r5 = _saf(res['5']); server_ip_port = _saf(r5.get('2')); udp_key = _saf(r5.get('3')); token = _saf(r5.get('4')); block_val = _saf(r5.get('1'))
                                if _saf(r5.get('42')): match_code = _saf(r5.get('42'))
                            if '1' in res: match_account_id = _saf(res['1'])
                            effective = match_account_id or account_id
                            if token and udp_key and match_code and server_ip_port:
                                async with _team_state["lock"]: all_peers = list(_team_state["peers"].keys())
                                if all_peers: await squad_sync.reset_match(all_peers)
                                thunder, sharma = await build_match_startup_packets(token, udp_key, match_code, effective, block_val or 0, server_ip=server_ip_port, region=account_region, client_version=client_version, access_token=current_account_data.get('access_token', ''))
                                match_index = await _inc_match(uid_str); bot_state.increment_match_started(); print_colored(f"[MATCH #{match_index}] UDP -> {server_ip_port}", Colors.CYAN); new_match = asyncio.create_task(play_game(server_ip_port, thunder, sharma, udp_key, match_code, effective, account_region, client_version, current_key, current_iv, match_index, on_match_complete=trigger_post_match_refresh)); play_matches.append(new_match)
                                async def drain_gw():
                                    while not new_match.done():
                                        try: await asyncio.wait_for(reader.read(4096), timeout=1.0)
                                        except Exception: break
                                drain_task = asyncio.create_task(drain_gw())
                                try: await new_match
                                except Exception: pass
                                finally: drain_task.cancel()
                                async with _team_state["lock"]:
                                    _team_state["peers"].pop(uid_str, None)
                                    if _team_state["leader_uid"] == uid_str: _team_state["leader_uid"] = None
                                await _team_member_leave(uid_str); _team_active["flag"] = True
                                try: writer.close(); await writer.wait_closed()
                                except Exception: pass
                                await asyncio.sleep(8.0); reconnect_count_total += 1; break
                        except Exception: pass
            except asyncio.CancelledError: raise
            except Exception as e:
                print_error(f"[FUNC] {uid_str}: {e}")
                if "Cache expired" in str(e): break
                reconnect_count_total += 1; await asyncio.sleep(bypass_human_reconnect_delay(reconnect_count_total % 5 + 1))
            finally:
                _team_active["flag"] = False
                for tk in (team_coord_task, member_trigger_task, guild_task, gateway_ping_task):
                    if tk and not tk.done(): tk.cancel()
                if writer:
                    try: writer.close(); await writer.wait_closed()
                    except Exception: pass
                async with _team_state["lock"]:
                    _team_state["peers"].pop(uid_str, None)
                    if _team_state["leader_uid"] == uid_str: _team_state["leader_uid"] = None
                await _team_member_leave(uid_str); _team_active["flag"] = True
    except asyncio.CancelledError: raise
_token_cache_memo = {}; _token_cache_memo_time = 0.0
def _json_serializer(obj): return {"__bytes_hex__": bytes(obj).hex()} if isinstance(obj, (bytes, bytearray)) else None
def _json_deserializer(obj):
    if isinstance(obj, dict):
        if "__bytes_hex__" in obj: return bytes.fromhex(obj["__bytes_hex__"])
        return {k: _json_deserializer(v) for k, v in obj.items()}
    if isinstance(obj, list): return [_json_deserializer(x) for x in obj]
    return obj
def _load_token_cache():
    global _token_cache_memo, _token_cache_memo_time
    if _token_cache_memo and (time.time() - _token_cache_memo_time) < 5.0: return _token_cache_memo
    if not os.path.exists(TOKEN_CACHE_FILE): return {}
    try:
        with open(TOKEN_CACHE_FILE, "r", encoding="utf-8") as f: data = json.loads(f.read().strip() or "{}")
        _token_cache_memo = _json_deserializer(data); _token_cache_memo_time = time.time(); return _token_cache_memo
    except Exception:
        try: os.remove(TOKEN_CACHE_FILE)
        except Exception: pass
        return {}
def _save_token_cache(cache):
    global _token_cache_memo, _token_cache_memo_time
    try:
        with open(TOKEN_CACHE_FILE, "w", encoding="utf-8") as f: json.dump(cache, f, indent=2, default=_json_serializer)
        _token_cache_memo = cache; _token_cache_memo_time = time.time()
    except Exception: pass
def cache_get(uid):
    cache = _load_token_cache(); e = cache.get(str(uid))
    if not e or time.time() - e.get("cached_at", 0) > TOKEN_CACHE_TTL: cache_invalidate(uid); return None
    if not isinstance(e.get("aes_ak"), (bytes, bytearray)) or len(e["aes_ak"]) != 16 or not isinstance(e.get("iv_i"), (bytes, bytearray)) or len(e["iv_i"]) != 16: cache_invalidate(uid); return None
    return e
def cache_set(uid, data):
    cache = _load_token_cache(); e = dict(data); e["cached_at"] = time.time(); cache[str(uid)] = e; _save_token_cache(cache)
def cache_invalidate(uid):
    cache = _load_token_cache()
    if str(uid) in cache: del cache[str(uid)]; _save_token_cache(cache)
async def refresh_account_profile(ad):
    try:
        url, token, rel, payload = ad.get('server_url'), ad.get('token'), ad.get('release_version'), ad.get('login_payload_data')
        if not (url and token and rel and payload): return
        res = await send_getlogin(payload, url, token, rel)
        if not res: return
        rp, dd = res; level, exp = int(get_proto_field(dd, 6, 1) or 1), int(get_proto_field(dd, 7, 0) or 0)
        if exp < EXP_TABLE.get(level, 0): exp += EXP_TABLE.get(level, 0)
        bot_state.update_exp(str(ad['account_id']), exp, level); ad['level'] = level; ad['exp'] = exp
    except Exception: pass
async def process_account_uid_pass(uid, password):
    cached = cache_get(uid)
    if cached: return cached
    vc = await version_config()
    if not vc: return None
    rel, cv, su = vc; tg = await get_access_token(uid, password)
    if not tg: return None
    oid, at, pf = tg; dev = get_device_for_account(uid); lpd = await build_majorlogin_payload(oid, at, pf, cv, dev); mresp = await send_majorlogin(lpd, rel, su)
    if mresp is None: return None
    gl = await send_getlogin(lpd, mresp.url, mresp.token, rel)
    if gl is None: return None
    rp, dd = gl; acc_id = str(mresp.account_id); level = int(get_proto_field(dd, 6, 1) or 1); exp = int(get_proto_field(dd, 7, 0) or 0); bot_state.register_account(uid=acc_id, nickname=rp.nickname or f"P_{acc_id}", region=mresp.region or "IND", level=level, exp=exp)
    ad = {'account_id': mresp.account_id, 'nickname': rp.nickname, 'region': mresp.region, 'level': level, 'exp': exp, 'open_id': oid, 'access_token': at, 'platform': str(pf), 'token': mresp.token, 'server_time': mresp.server_time, 'aes_ak': mresp.aes_ak, 'iv_i': mresp.iv_i, 'functional_addrs': rp.functional_addrs, 'informational_addrs': rp.informational_addrs, 'release_version': rel, 'client_version': cv, 'server_url': mresp.url, 'login_payload_data': lpd, 'auth_type': 'guest', 'auth_uid': uid, 'auth_password': password}
    bot_state.account_credentials[acc_id] = ad; bot_state.account_credentials[str(uid)] = ad; cache_set(uid, ad); return ad
async def informational(addrs, starter_packet, key, iv, region="IND"):
    while True:
        try:
            ip, port = addrs.split(":"); rip = await resolve_host_cloudflare(ip); reader, writer = await asyncio.open_connection(rip, int(port)); writer.write(bytes.fromhex(starter_packet)); await writer.drain()
            async def ka():
                ka_b = await send_keep_alive(region)
                while True: await asyncio.sleep(2.0); writer.write(ka_b); await writer.drain()
            asyncio.create_task(ka())
            while True:
                if not await reader.read(8192): break
        except Exception: await asyncio.sleep(2.0)
async def run_account_worker(ad, label):
    acc_id = str(ad['account_id']); info_task = None; exp_task = None
    try:
        reg = ad.get('region', 'IND'); tcp_online = await build_tcp_startup_packet(ad['account_id'], ad['token'], ad['server_time'], ad['aes_ak'], ad['iv_i'], region=reg, typ='OnLine'); tcp_chat = await build_tcp_startup_packet(ad['account_id'], ad['token'], ad['server_time'], ad['aes_ak'], ad['iv_i'], region=reg, typ='ChaT'); info_task = asyncio.create_task(informational(ad['informational_addrs'], tcp_chat, ad['aes_ak'], ad['iv_i'], region=reg))
        async def exp_refresher():
            while True: await asyncio.sleep(EXP_REFRESH_INTERVAL); await refresh_account_profile(ad)
        exp_task = asyncio.create_task(exp_refresher()); await functional_battle_royale(ad['functional_addrs'], tcp_online, reg, ad['client_version'], ad['aes_ak'], ad['iv_i'], account_id=acc_id, account_data=ad)
    except Exception: pass
    finally:
        for t in (info_task, exp_task):
            if t and not t.done(): t.cancel()
async def account_loop_guest(uid, password):
    while BOT_RUNNING:
        try:
            ad = await process_account_uid_pass(uid, password)
            if not ad: await asyncio.sleep(15); continue
            await run_account_worker(ad, uid); await asyncio.sleep(3)
        except asyncio.CancelledError: break
        except Exception as e: print_error(f"Account loop error: {e}"); await asyncio.sleep(10)
EXP_TABLE = {1:0,2:48,3:202,4:544,5:1012,6:1844,7:2792,8:3800,9:4870,10:6004,11:7192,12:8448,13:9760,14:11140,15:12566,16:14060,17:15610,18:17224,19:18902,20:20632,21:22424,22:24278,23:26192,24:28166,25:30200,26:32294,27:34448,28:37804,29:41274,30:44870,31:48582,32:53394,33:58566,34:64096,35:69994,36:76460,37:83506,38:91128,39:99322,40:108092,41:120144,42:133266,43:147472,44:162760,45:179126,46:196572,47:215368,48:235516,49:257010,50:279860,51:304056,52:348318,53:394982,54:444044,55:495508,56:549364,57:633756,58:721744,59:813336,60:908522,61:1041438,62:1180352,63:1325266,64:1476184,65:1634300,66:1840946,67:2056594,68:2281242,69:2514880,70:2757530,71:3059506,72:3372284,73:3699456,74:4041030,75:4397002,76:4829104,77:5282204,78:5756304,79:6251408,80:6776502,81:7381324,82:8043154,83:8752982,84:9510808,85:10316338,86:11277190,87:12291748,88:13360304,89:14482858,90:15659418,91:17026708,92:18453950,93:19941280,94:21488570,95:23095858,96:24763138,97:26490428,98:28378704,99:30124996,100:32032884}
def calculate_level_progress(level, current_exp):
    level = max(1, level); next_level = min(100, level + 1); base_exp = EXP_TABLE.get(level, 0); target_exp = EXP_TABLE.get(next_level, base_exp + 50000)
    needed, earned, remaining = max(1, target_exp - base_exp), max(0, current_exp - base_exp), max(0, target_exp - current_exp)
    return {"next_level": next_level, "base_exp": base_exp, "target_exp": target_exp, "needed_for_level": needed, "earned_in_level": earned, "remaining_exp": remaining, "progress_pct": round(min(100.0, max(0.0, (earned / needed) * 100.0)), 1)}
class BotState:
    def __init__(self):
        self.accounts = {}; self.logs = []; self.max_logs = 200; self.total_matches = 0; self.total_matches_started = 0; self.total_gained_exp = 0; self.start_time = time.time(); self.account_workers = {}; self.paused_accounts = set(); self.refresh_callbacks = {}; self.account_credentials = {}
    def log(self, message, level="info", uid=None):
        self.logs.append({"time": time.strftime("%H:%M:%S"), "level": level, "message": message, "uid": str(uid) if uid else None})
        if len(self.logs) > self.max_logs: self.logs.pop(0)
    def register_account(self, uid, nickname, region, level, exp, likes=0, token=None, auth_uid=None):
        uid_str = str(uid); prog = calculate_level_progress(level or 1, exp); self.accounts[uid_str] = {"uid": uid_str, "nickname": nickname, "region": region, "level": level, "initial_exp": exp, "current_exp": exp, "gained_exp": 0, "progress_pct": prog["progress_pct"], "remaining_exp": prog["remaining_exp"], "matches_played": 0, "active_matches": 0, "status": "ONLINE", "is_paused": False, "start_time": time.time()}; self.recalc_totals()
    def update_exp(self, uid, current_exp, level=None):
        if str(uid) in self.accounts:
            acc = self.accounts[str(uid)]; old_exp = acc["current_exp"]; acc["current_exp"] = current_exp
            if level: acc["level"] = level
            if acc["initial_exp"] == 0 and current_exp > 0: acc["initial_exp"] = current_exp
            acc["gained_exp"] = max(0, current_exp - acc["initial_exp"]); prog = calculate_level_progress(acc["level"], current_exp); acc["progress_pct"] = prog["progress_pct"]; acc["remaining_exp"] = prog["remaining_exp"]; self.recalc_totals()
    def update_status(self, uid, status, active_matches=None):
        if str(uid) in self.accounts: self.accounts[str(uid)]["status"] = status; 
        if active_matches is not None and str(uid) in self.accounts: self.accounts[str(uid)]["active_matches"] = active_matches
    def is_paused(self, uid): return str(uid) in self.paused_accounts
    def toggle_pause(self, uid):
        uid = str(uid)
        if self.is_paused(uid): self.paused_accounts.remove(uid); self.accounts[uid]["status"] = "ONLINE"; return False
        else: self.paused_accounts.add(uid); self.accounts[uid]["status"] = "PAUSED"; return True
    def increment_match_started(self): self.total_matches_started += 1
    def increment_match(self, uid):
        self.total_matches += 1
        if str(uid) in self.accounts: self.accounts[str(uid)]["matches_played"] += 1
    def recalc_totals(self): self.total_gained_exp = sum(acc.get("gained_exp", 0) for acc in self.accounts.values())
bot_state = BotState()
INDEX_HTML = r"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Kanha Bot</title><style>body{background:#0a0a12;color:#fff;font-family:sans-serif;padding:20px}table{width:100%;border-collapse:collapse}th,td{padding:10px;border-bottom:1px solid #333}</style></head><body><h1>Kanha Bot</h1><table><thead><tr><th>UID</th><th>Level</th><th>EXP</th><th>Status</th></tr></thead><tbody id="tbody"></tbody></table><script>setInterval(()=>fetch('/api/stats').then(r=>r.json()).then(d=>{document.getElementById('tbody').innerHTML=d.accounts.map(a=>`<tr><td>${a.uid}</td><td>${a.level}</td><td>${a.gained_exp}</td><td>${a.status}</td></tr>`).join('')}),3000)</script></body></html>"""
async def start_web():
    from aiohttp import web
    async def stats(r): return web.json_response({"accounts": list(bot_state.accounts.values())})
    app = web.Application(); app.router.add_get("/", lambda r: web.Response(text=INDEX_HTML, content_type="text/html")); app.router.add_get("/api/stats", stats); runner = web.AppRunner(app); await runner.setup(); await web.TCPSite(runner, "0.0.0.0", WEB_PORT).start()

# ═══════════════════════════ TELEGRAM BOT CONTROL ═══════════════════════════
from aiogram import Bot as TgBot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

TG_TOKEN = "8244534907:AAEnRgFtBHUDtn_E8WOIMop0JpGLZnBbCig"
ADMIN_ID = 7424554376

tg_bot = TgBot(token=TG_TOKEN)
dp = Dispatcher()

class Form(StatesGroup):
    waiting_for_creds = State()

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

async def run_telegram():
    print("[ERIS] Telegram Bot Started.")
    await dp.start_polling(tg_bot)

async def main():
    print_colored("=" * 60, Colors.CYAN); print_colored("  KANHA BOT — FINAL COMPLETE CODE", Colors.GREEN); print_colored("=" * 60, Colors.CYAN)
    asyncio.create_task(run_telegram())
    await start_web(); print_success(f"Dashboard: http://localhost:{WEB_PORT}")
    try:
        while True: await asyncio.sleep(1)
    except KeyboardInterrupt: pass

if __name__ == "__main__":
    asyncio.run(main())
