# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════════════
#  TEAM RBC — ULTIMATE BRUTAL SQUAD BOT (Real Guild Sync, IND Server)
# ═══════════════════════════════════════════════════════════════════
import sys, asyncio, httpx, random, json, socket, struct, time, os, uuid
import itertools, secrets, traceback, base64, math, html
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

from aiogram import Bot as TgBot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup

from google_play_scraper import app as play_scraper
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from protobuf_decoder.protobuf_decoder import Parser
from message_ids import MESSAGE_ID_TO_NAME
import RbcTeam_pb2
import RbcFF_pb2
import thunderFF_pb2

from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder

from dashboard_server import bot_state, start_web_dashboard

# ═══════════════════════════ GUILD PROTOBUF (REQCLAN) ═══════════════════════════
_sym_db = _symbol_database.Default()
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(
    b'\n\rreqClan.proto"\x1c\n\tMyMessage\x12\x0f\n\x07\x66ield_1\x18\x01 \x01(\x03\x62\x06proto3'
)
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'reqClan_pb2', _globals)
MyMessage = _sym_db.GetSymbol('MyMessage')

# ═══════════════════════════ CONFIG ═══════════════════════════
TG_TOKEN = os.environ.get("TG_TOKEN", "8244534907:AAGFRq82LdJqwIc22K8dBm9kJ7wG21OYNmo")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7424554376"))

FORCE_CHANNEL_ID = "-1003725624623"
FORCE_CHANNEL_LINK = "https://t.me/+Qw8U-azwpbFjYmQ1"

WEB_HOST = "0.0.0.0"
WEB_PORT = int(os.environ.get("PORT", 20333))
ACCOUNTS_FILE = "accounts.json"
TOKEN_CACHE_FILE = "token_cache.json"
DEVICES_FILE = "devices.json"
TOKEN_CACHE_TTL = 4500

START_MATCH_INTERVAL    = 4.0
NEW_MATCH_DELAY         = 8.0   
MAX_MATCH_DURATION      = 3000
MATCH_IDLE_TIMEOUT      = 90.0
EXP_REFRESH_INTERVAL    = 30.0
EXP_REFRESH_AFTER_MATCH_DELAY = 60.0   
MAX_CONSECUTIVE_PARSE_FAILURES = 5
NON_MATCH_RECONNECT_DELAY      = 1.0

DEATH_WAIT_SECONDS      = 120.0   
MATCH_END_WAIT_SECONDS  = 60.0    
SQUAD_SYNC_TIMEOUT      = 360.0   

BR_MODE_ID             = 1
BR_MAP_ID              = 1

ANTI_AFK_MIN_INTERVAL  = 1.8
ANTI_AFK_MAX_INTERVAL  = 3.5

MATCH_SEARCH_TIMEOUT   = 300.0
MATCH_WATCHDOG_CHECK   = 45.0

# FORCED IND SERVER
REGION_ROTATION_LIST   = ["IND", "IND", "IND", "IND", "IND"]
REGION_ROTATE_EVERY_N  = 3
MAX_SEARCH_ATTEMPTS    = 25

SAFE_PLAY_MODE        = True
BYPASS_TIMING_JITTER  = True
BYPASS_PACKET_JITTER  = True
BYPASS_HELLO_DELAY    = True
BYPASS_KA_JITTER      = True

ENABLE_SPEED_MOVEMENT       = True
MOVEMENT_SPEED_MIN          = 1.0
MOVEMENT_SPEED_MAX          = 1.4
MOVEMENT_PATTERN            = "circle"
MOVEMENT_TICK_MS            = 240
MOVEMENT_RADIUS             = 180
MOVEMENT_UPDATE_SPEED_EVERY = 4.0

ENABLE_HTTP_PING = False

FALLBACK_UID = ""
FALLBACK_PASSWORD = ""

# ═══════════════════════════ SQUAD CONFIG ═══════════════════════════
TEAM_MODE               = True
TEAM_SIZE               = 4
TEAM_PEER_WAIT_TIMEOUT  = 90.0  
TEAM_CREATE_WAIT        = 5.0   
TEAM_INVITE_CYCLE_WAIT  = 5.0
TEAM_INVITE_MAX_TIME    = 60.0
TEAM_HEARTBEAT_INTERVAL = 3.0
TEAM_IDLE_ITERS_TEAM    = 3600
TEAM_MEMBER_START_DELAY = 20.0
TEAM_FINAL_WAIT         = 8.0   
TEAM_READY_DELAY        = 5.0
_accept_friend_request  = True
DEBUG_TEAM_PACKETS      = False

# ── GUILD CONFIG ──
GUILD_UID = os.environ.get("GUILD_UID", "3055649830")
GUILD_JOIN_RETRY_INTERVAL = 15.0
GUILD_JOIN_MAX_ATTEMPTS = 6
GUILD_APPROVE_INTERVAL = 15.0
ACCOUNT_GUILD_OVERRIDES = {}

# ═══════════════════════════ SQUAD MATCH SYNC ═══════════════════════════
class SquadMatchSync:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.active_squad_uids = set()
        self.dead_squad_uids = set()
        self.all_dead_event = asyncio.Event()

    async def reset_match(self, uids: List[str]):
        async with self.lock:
            self.active_squad_uids = set(str(u) for u in uids)
            self.dead_squad_uids.clear()
            self.all_dead_event.clear()
            print_info(f"[SQUAD SYNC] Match started with {len(self.active_squad_uids)} active bots.")

    async def mark_bot_dead(self, uid: str):
        async with self.lock:
            uid = str(uid)
            if uid in self.active_squad_uids:
                self.dead_squad_uids.add(uid)
                alive_left = len(self.active_squad_uids) - len(self.dead_squad_uids)
                print_warning(f"[SQUAD SYNC] Bot {uid} DEAD. Alive bots remaining: {alive_left}")
                if len(self.dead_squad_uids) >= len(self.active_squad_uids):
                    print_success("[SQUAD SYNC] ALL 4 BOTS ARE DEAD! Exiting game together.")
                    self.all_dead_event.set()

    async def wait_for_all_dead(self, timeout=SQUAD_SYNC_TIMEOUT):
        try:
            await asyncio.wait_for(self.all_dead_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            print_warning("[SQUAD SYNC] Timeout reached while waiting for remaining bots.")

squad_sync = SquadMatchSync()


# ═══════════════════════════ ACCOUNTS PURGE ═══════════════════════════
def purge_extra_accounts_from_file(keep_uids: set):
    if not os.path.exists(ACCOUNTS_FILE):
        return
    try:
        expanded_keep = set(str(u) for u in keep_uids)
        for gid in list(keep_uids):
            gid_s = str(gid)
            try:
                auth = bot_state.game_to_auth_id.get(gid_s)
                if auth: expanded_keep.add(str(auth))
            except Exception: pass
            try:
                game = bot_state.auth_to_game_id.get(gid_s)
                if game: expanded_keep.add(str(game))
            except Exception: pass
            try:
                cred = bot_state.account_credentials.get(gid_s)
                if cred:
                    for key in ('auth_uid', 'account_id', 'uid'):
                        if cred.get(key):
                            expanded_keep.add(str(cred[key]))
            except Exception: pass

        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list) or len(data) == 0:
            return

        filtered = []
        for acc in data:
            acc_uid = str(acc.get("uid", "")).strip()
            acc_auth = str(acc.get("auth_uid", "")).strip()
            acc_game = str(acc.get("account_id", "")).strip()
            if (acc_uid and acc_uid in expanded_keep) \
               or (acc_auth and acc_auth in expanded_keep) \
               or (acc_game and acc_game in expanded_keep):
                filtered.append(acc)

        if len(filtered) == 0 or len(filtered) == len(data):
            return

        tmp_file = ACCOUNTS_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(filtered, f, indent=2)
        os.replace(tmp_file, ACCOUNTS_FILE)
        print_success(f"[CLEANUP] Purged {len(data) - len(filtered)} extra. Kept {len(filtered)}.")
    except Exception as e:
        print_error(f"[CLEANUP] {e}")


# ═══════════════════════════ ANTI-BAN ═══════════════════════════
def bypass_jitter(base, spread=0.35):
    if not (SAFE_PLAY_MODE and BYPASS_TIMING_JITTER): return base
    return max(0.05, base + random.uniform(-spread, spread))

def bypass_packet_jitter(base, spread_ratio=0.35):
    if not (SAFE_PLAY_MODE and BYPASS_PACKET_JITTER): return base
    return max(0.1, base + random.uniform(-base * spread_ratio, base * spread_ratio))

def bypass_hello_delay():
    if not (SAFE_PLAY_MODE and BYPASS_HELLO_DELAY): return 0.0
    return random.uniform(0.05, 0.45)

def bypass_ka_jitter(base=5.0):
    if not (SAFE_PLAY_MODE and BYPASS_KA_JITTER): return base
    return max(3.0, base + random.uniform(-0.8, 1.2))

def bypass_human_reconnect_delay(attempt):
    if not (SAFE_PLAY_MODE and BYPASS_TIMING_JITTER): return min(attempt * 0.5, 2.0)
    return max(0.05, min(attempt * 0.5, 2.0) + random.uniform(-0.4, 0.7))


# ═══════════════════════════ DEVICE ═══════════════════════════
def get_device_for_account(account_identifier):
    devices = {}
    if os.path.exists(DEVICES_FILE):
        try:
            with open(DEVICES_FILE, "r", encoding="utf-8") as f:
                devices = json.load(f)
        except Exception: pass
    key = str(account_identifier)
    if key in devices: return devices[key]
    dev_list = [
        ("Samsung", "SM-G998B", "Adreno (TM) 660", "Android OS 12 / API-31"),
        ("Xiaomi", "2201122G", "Adreno (TM) 730", "Android OS 13 / API-33"),
        ("Realme", "RMX3700", "Mali-G710", "Android OS 14 / API-34"),
        ("OnePlus", "CPH2451", "Adreno (TM) 740", "Android OS 13 / API-33"),
        ("OPPO", "CPH2611", "Adreno (TM) 720", "Android OS 14 / API-34"),
    ]
    brand, model, gpu, os_ver = random.choice(dev_list)
    dev = {
        "unique_device_id": f"Google|{uuid.uuid4()}",
        "brand": brand, "model": model, "gpu_renderer": gpu, "system_software": os_ver,
        "screen_width": random.choice([1080, 1440, 720]),
        "screen_height": random.choice([2400, 3200, 1600]),
        "screen_dpi": str(random.randint(300, 420)),
        "memory": random.randint(2800, 6500),
        "processor_details": f"ARM64 FP ASIMD AES | {random.randint(2200, 3200)} | {random.randint(6, 12)}",
        "client_ip": f"{random.randint(103, 223)}.{random.randint(10, 250)}.{random.randint(10, 250)}.{random.randint(10, 250)}",
    }
    devices[key] = dev
    try:
        with open(DEVICES_FILE, "w", encoding="utf-8") as f:
            json.dump(devices, f, indent=2)
    except Exception: pass
    return dev


# ═══════════════════════════ DNS / SOCKET ═══════════════════════════
_DNS_CACHE: Dict[str, Tuple[str, float]] = {}
_DNS_CACHE_TTL = 300.0

async def resolve_host_cloudflare(hostname):
    if not hostname: return hostname
    parts = hostname.split('.')
    if len(parts) == 4 and all(p.isdigit() for p in parts): return hostname
    now = time.time()
    if hostname in _DNS_CACHE:
        ip, exp = _DNS_CACHE[hostname]
        if now < exp: return ip
    try:
        loop = asyncio.get_running_loop()
        info = await loop.getaddrinfo(hostname, None, family=socket.AF_INET)
        if info:
            ip = info[0][4][0]
            _DNS_CACHE[hostname] = (ip, now + _DNS_CACHE_TTL)
            return ip
    except Exception: pass
    return hostname

def optimize_tcp_socket(sock):
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
    except Exception: pass

def optimize_udp_socket(sock):
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 131072)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 131072)
    except Exception: pass


# ═══════════════════════════ HTTP CLIENT ═══════════════════════════
client = httpx.AsyncClient(verify=False, timeout=10.0,
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=50))
headers = {
    'User-Agent': 'UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
    'Connection': 'Keep-Alive', 'Accept-Encoding': 'gzip',
    'Content-Type': 'application/x-www-form-urlencoded',
    'X-Unity-Version': '2018.4.12f1', 'X-GA-SV': '1789535859',
    'X-GA': 'v1 1', 'ReleaseVersion': 'OB55'
}

AES_KEY = b'Yg&tc%DEuh6%Zc^8'
AES_IV  = b'6oyZDr22E3ychjM%'

CRC7_TABLE = bytes([
    0,9,18,27,36,45,54,63,72,65,90,83,108,101,126,119,25,16,11,2,61,52,47,38,
    81,88,67,74,117,124,103,110,50,59,32,41,22,31,4,13,122,115,104,97,94,87,76,69,
    43,34,57,48,15,6,29,20,99,106,113,120,71,78,85,92,100,109,118,127,64,73,82,91,
    44,37,62,55,8,1,26,19,125,116,111,102,89,80,75,66,53,60,39,46,17,24,3,10,
    86,95,68,77,114,123,96,105,30,23,12,5,58,51,40,33,79,70,93,84,107,98,121,112,
    7,14,21,28,35,42,49,56,65,72,83,90,101,108,119,126,9,0,27,18,45,36,63,54,
    88,81,74,67,124,117,110,103,16,25,2,11,52,61,38,47,115,122,97,104,87,94,69,76,
    59,50,41,32,31,22,13,4,106,99,120,113,78,71,92,85,34,43,48,57,6,15,20,29,
    37,44,55,62,1,8,19,26,109,100,127,118,73,64,91,82,60,53,46,39,24,17,10,3,
    116,125,102,111,80,89,66,75,23,30,5,12,51,58,33,40,95,86,77,68,123,114,105,96,
    14,7,28,21,42,35,56,49,70,79,84,93,98,107,112,121,
])
_DELTA = 0x9E3779B9
_ROUNDS = 16
_FIELD_SIZES = {0:1, 1:2, 2:2, 3:1, 4:2}
_FIELD_NAMES = {0:"sendOption", 1:"cmd", 2:"orderId", 3:"flags", 4:"length"}


# ═══════════════════════════ LOG ═══════════════════════════
class Colors:
    GREEN='\033[92m'; FAIL='\033[91m'; WARNING='\033[93m'
    CYAN='\033[96m'; MAGENTA='\033[95m'; WHITE='\033[97m'; ENDC='\033[0m'

def print_colored(t, c=Colors.WHITE):
    try: print(f"{c}{t}{Colors.ENDC}")
    except Exception: pass

def print_success(t):
    print_colored(f"[+] {t}", Colors.GREEN)
    try: bot_state.log(t, "success")
    except Exception: pass

def print_error(t):
    print_colored(f"[-] {t}", Colors.FAIL)
    try: bot_state.log(t, "error")
    except Exception: pass

def print_warning(t):
    print_colored(f"[!] {t}", Colors.WARNING)
    try: bot_state.log(t, "warning")
    except Exception: pass

def print_info(t):
    print_colored(f"[i] {t}", Colors.CYAN)
    try: bot_state.log(t, "info")
    except Exception: pass

def get_proto_field(d, key, default=None):
    if not d or not isinstance(d, dict): return default
    if key in d:
        v = d[key].get('data'); return v if v is not None else default
    if str(key) in d:
        v = d[str(key)].get('data'); return v if v is not None else default
    return default


# ═══════════════════════════ MATCH COUNTER ═══════════════════════════
_match_counters: Dict[str, int] = {}
_match_counter_lock = asyncio.Lock()

async def _inc_match(uid):
    async with _match_counter_lock:
        _match_counters[uid] = _match_counters.get(uid, 0) + 1
        return _match_counters[uid]

async def _dec_match(uid):
    async with _match_counter_lock:
        if uid in _match_counters and _match_counters[uid] > 0:
            _match_counters[uid] -= 1
        return _match_counters.get(uid, 0)

async def _get_match_count(uid):
    async with _match_counter_lock:
        return _match_counters.get(uid, 0)

async def _get_total_match_count():
    async with _match_counter_lock:
        return sum(_match_counters.values())


# ═══════════════════════════ SQUAD STATE ═══════════════════════════
_team_state = {
    "peers": {},
    "leader_uid": None,
    "team_code": None,
    "pk_code": None,
    "members": set(),
    "members_lock": asyncio.Lock(),
    "lock": asyncio.Lock(),
}

async def _team_member_join(uid):
    uid = str(uid)
    async with _team_state["members_lock"]:
        before = len(_team_state["members"])
        _team_state["members"].add(uid)
        after = len(_team_state["members"])
    if after != before:
        print_success(f"[TEAM] 👥 In team ({after}/{TEAM_SIZE}) | joined: {uid}")
        try:
            for p_uid in list(_team_state["peers"].keys()):
                role = "LEADER" if _team_state["leader_uid"] == p_uid else "MEMBER"
                joined = p_uid in _team_state["members"]
                tag = f"IN_TEAM ({after}/{TEAM_SIZE}) [{role}]" if joined else f"JOINING ({after}/{TEAM_SIZE}) [{role}]"
                bot_state.update_status(p_uid, tag, 0)
        except Exception: pass
    return after

async def _team_member_leave(uid):
    async with _team_state["members_lock"]:
        _team_state["members"].discard(str(uid))

async def _team_member_count():
    async with _team_state["members_lock"]:
        return len(_team_state["members"])

async def _team_member_reset(keep_leader=True):
    async with _team_state["members_lock"]:
        _team_state["members"].clear()
        if keep_leader and _team_state["leader_uid"]:
            _team_state["members"].add(_team_state["leader_uid"])


# ═══════════════════════════ TOKEN CACHE ═══════════════════════════
_token_cache_memo = {}
_token_cache_memo_time = 0.0
_TOKEN_CACHE_MEMO_TTL = 5.0

def _json_serializer(obj):
    if isinstance(obj, (bytes, bytearray)): return {"__bytes_hex__": bytes(obj).hex()}
    raise TypeError(f"not serializable: {type(obj)}")

def _json_deserializer(obj):
    if isinstance(obj, dict):
        if "__bytes_hex__" in obj and len(obj) == 1:
            try: return bytes.fromhex(obj["__bytes_hex__"])
            except Exception: return b""
        return {k: _json_deserializer(v) for k, v in obj.items()}
    if isinstance(obj, list): return [_json_deserializer(x) for x in obj]
    return obj

def _load_token_cache():
    global _token_cache_memo, _token_cache_memo_time
    now = time.time()
    if _token_cache_memo and (now - _token_cache_memo_time) < _TOKEN_CACHE_MEMO_TTL:
        return _token_cache_memo
    if not os.path.exists(TOKEN_CACHE_FILE): return {}
    try:
        with open(TOKEN_CACHE_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content: return {}
        data = json.loads(content)
        if not isinstance(data, dict): raise ValueError("root must be dict")
        parsed = _json_deserializer(data)
        _token_cache_memo = parsed; _token_cache_memo_time = now
        return parsed
    except Exception as e:
        print_error(f"Token cache corrupt -> delete: {e}")
        try: os.remove(TOKEN_CACHE_FILE)
        except Exception: pass
        return {}

def _save_token_cache(cache):
    global _token_cache_memo, _token_cache_memo_time
    try:
        tmp = TOKEN_CACHE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, default=_json_serializer)
        os.replace(tmp, TOKEN_CACHE_FILE)
        _token_cache_memo = cache; _token_cache_memo_time = time.time()
    except Exception as e: print_error(f"Cache save: {e}")

def cache_get(uid):
    cache = _load_token_cache()
    e = cache.get(str(uid))
    if not e: return None
    if time.time() - e.get("cached_at", 0) > TOKEN_CACHE_TTL:
        cache_invalidate(uid); return None
    if str(e.get("account_id", "")).isdigit(): e["account_id"] = int(e["account_id"])
    if not isinstance(e.get("login_payload_data"), (bytes, bytearray)):
        cache_invalidate(uid); return None
    return e

def cache_set(uid, data):
    cache = _load_token_cache()
    e = dict(data); e["cached_at"] = time.time()
    cache[str(uid)] = e; _save_token_cache(cache)
    print_success(f"[CACHE] Saved UID {uid}")

def cache_invalidate(uid):
    cache = _load_token_cache()
    if str(uid) in cache:
        del cache[str(uid)]; _save_token_cache(cache)

def _update_cache_profile(data, level, exp):
    try:
        keys = []
        if data.get('auth_uid'): keys.append(str(data['auth_uid']))
        if data.get('auth_token'): keys.append(f"tok_{data['auth_token'][:20]}")
        if not keys: return
        cache = _load_token_cache(); ch = False
        for k in keys:
            if k in cache and isinstance(cache[k], dict):
                cache[k]['level'] = level; cache[k]['exp'] = exp; ch = True
        if ch: _save_token_cache(cache)
    except Exception: pass


# ═══════════════════════════ ENCRYPTION ═══════════════════════════
async def aes_encrypt(payload, key, iv):
    return AES.new(key, AES.MODE_CBC, iv).encrypt(pad(payload, AES.block_size))

async def get_playstore_version():
    loop = asyncio.get_event_loop()
    res = await loop.run_in_executor(None, lambda: play_scraper('com.dts.freefireth', lang='hi', country='id'))
    return res.get("version")

async def version_config():
    app_version = await get_playstore_version()
    url = ("https://version.ggwhitehawk.com/live/ver.php"
           f"?version={app_version}&lang=hi&device=android&channel=android"
           "&appstore=googleplay&region=IND&whitelist_version=1.3.0&whitelist_sp_version=1.0.0")
    try:
        r = await client.get(url); r.raise_for_status()
        d = r.json()
        su = d.get("server_url"); rv = d.get("remote_version"); lr = d.get("latest_release_version")
        if not su or not rv or not lr: return None
        return lr, rv, su
    except Exception: return None

async def get_access_token(uid, password):
    url = "https://100067.connect.garena.com/oauth/guest/token/grant"
    hdrs = {
        "Host": "100067.connect.garena.com",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12; SM-G998B)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip, deflate, br", "Connection": "close"
    }
    data = {
        "uid": uid, "password": password, "response_type": "token", "client_type": "2",
        "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
        "client_id": "100067"
    }
    for attempt in range(5):
        try:
            r = await client.post(url, headers=hdrs, data=data)
            if r.status_code == 200:
                d = r.json()
                oid = d.get("open_id"); at = d.get("access_token"); pf = d.get("platform", 4)
                if oid and at: return oid, at, pf
            if r.status_code == 429: await asyncio.sleep(1); continue
        except Exception: pass
        await asyncio.sleep(0.5)
    return None

async def parse_results(parsed):
    out = {}
    for r in parsed:
        fd = {"wire_type": r.wire_type}
        if r.wire_type in ("varint", "string", "bytes"): fd["data"] = r.data
        elif r.wire_type == "length_delimited":
            fd["data"] = await parse_results(r.data.results)
        out[r.field] = fd
    return out

async def decode_protobuf(data):
    parsed = Parser().parse(data)
    return json.dumps(await parse_results(parsed))

def decode_protobuf_dict_safe(data):
    try:
        parsed = Parser().parse(data)
        return _recursive_dict(parsed)
    except Exception: return {}

def _recursive_dict(results):
    out = {}
    for r in results:
        fd = {"wire_type": r.wire_type}
        if r.wire_type in ("varint", "string", "bytes"): fd["data"] = r.data
        elif r.wire_type == "length_delimited":
            if hasattr(r.data, "results"): fd["data"] = _recursive_dict(r.data.results)
            elif isinstance(r.data, list): fd["data"] = _recursive_dict(r.data)
            else: fd["data"] = str(r.data)
        out[str(r.field)] = fd
    return out

def _decode_proto_manual(data):
    result = {}; offset = 0; data_len = len(data)
    while offset < data_len:
        header = 0; shift = 0
        while offset < data_len:
            b = data[offset]; offset += 1
            header |= (b & 0x7F) << shift
            if not (b & 0x80): break
            shift += 7
            if shift > 28: break
        if header == 0: break
        fn = header >> 3; wt = header & 0x7
        if fn == 0: break
        if wt == 0:
            v = 0; shift = 0
            while offset < data_len:
                b = data[offset]; offset += 1
                v |= (b & 0x7F) << shift
                if not (b & 0x80): break
                shift += 7
                if shift > 63: break
            result[fn] = v
        elif wt == 2:
            length = 0; shift = 0
            while offset < data_len:
                b = data[offset]; offset += 1
                length |= (b & 0x7F) << shift
                if not (b & 0x80): break
                shift += 7
                if shift > 28: break
            if length > data_len - offset: break
            value = data[offset:offset+length]; offset += length
            try:
                s = value.decode('utf-8')
                if s and all(31 < ord(c) < 127 or ord(c) in (9,10,13) for c in s):
                    result[fn] = s
                else:
                    nested = _decode_proto_manual(value)
                    result[fn] = nested if nested else value.hex()
            except UnicodeDecodeError:
                nested = _decode_proto_manual(value)
                result[fn] = nested if nested else value.hex()
        elif wt == 5: offset += 4
        elif wt == 1: offset += 8
        else: break
    return result


# ═══════════════════════════ PROTOBUF ENCODE ═══════════════════════════
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
        if isinstance(v, dict):
            nested = build_proto(v)
            parts.append(encode_varint((k << 3) | 2) + encode_varint(len(nested)) + nested)
        elif isinstance(v, int):
            parts.append(encode_varint((k << 3) | 0) + encode_varint(v))
        elif isinstance(v, (str, bytes)):
            ev = v.encode() if isinstance(v, str) else v
            parts.append(encode_varint((k << 3) | 2) + encode_varint(len(ev)) + ev)
    return b''.join(parts)

def encrypt_api(plain_hex):
    return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(
        pad(bytes.fromhex(plain_hex), AES.block_size)).hex()

def encrypt_api_bytes(plain_bytes):
    return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(plain_bytes, AES.block_size))


# ═══════════════════════════ SQUAD PROTOBUF BUILDERS ═══════════════════════════
def _pb_varint(fn, val): return encode_varint((fn << 3) | 0) + encode_varint(val)
def _pb_length(fn, val):
    enc = val.encode('utf-8') if isinstance(val, str) else val
    return encode_varint((fn << 3) | 2) + encode_varint(len(enc)) + enc

def create_proto(fields):
    packet = bytearray()
    for field, value in fields.items():
        if isinstance(field, str): field = int(field)
        if isinstance(value, dict):
            packet.extend(_pb_length(field, bytes(create_proto(value))))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    packet.extend(_pb_length(field, bytes(create_proto(item))))
                elif isinstance(item, str): packet.extend(_pb_length(field, item))
                elif isinstance(item, (bytes, bytearray)): packet.extend(_pb_length(field, bytes(item)))
                elif isinstance(item, bool): packet.extend(_pb_varint(field, 1 if item else 0))
                elif isinstance(item, int): packet.extend(_pb_varint(field, item))
        elif isinstance(value, bool): packet.extend(_pb_varint(field, 1 if value else 0))
        elif isinstance(value, int): packet.extend(_pb_varint(field, value))
        elif isinstance(value, str): packet.extend(_pb_length(field, value))
        elif isinstance(value, (bytes, bytearray)): packet.extend(_pb_length(field, bytes(value)))
    return bytes(packet)

def create_packet(Pk, N, K, V):
    if isinstance(K, str): K = bytes.fromhex(K) if len(K) == 32 else K.encode()
    if isinstance(V, str): V = bytes.fromhex(V) if len(V) == 32 else V.encode()
    PkEnc = AES.new(K, AES.MODE_CBC, V).encrypt(pad(bytes.fromhex(Pk), 16)).hex()
    L = len(PkEnc) // 2
    hexlen = hex(L)[2:]
    if len(hexlen) % 2 != 0: hexlen = '0' + hexlen
    pad_len = 12 - len(N) - len(hexlen)
    if pad_len < 0: pad_len = 0
    return bytes.fromhex(N + ('0' * pad_len) + hexlen + PkEnc)


# ═══════════ SQUAD PACKETS ═══════════
def create_team(key, iv, game_version="1.132.9"):
    fields = {
        1: 1, 2: {2: bytes.fromhex("01"), 3: 1, 4: 3, 5: "en",
            8: {1: "IDC3", 2: 123, 3: "IND"}, 9: 1,
            10: bytes.fromhex("01090a0b1219202729"), 11: 2, 13: 1,
            14: {1: "08FBA33B4BABE2790205390333330000009700050092005F72697EB2134DCBB2467625142201040e38e848dc0e748c3f6aa04d81000000ff1113090dcacfa16d",
                 2: 478, 3: "7e585d55", 4: "y[Z]", 6: 12, 7: "15686677735a7506101c",
                 8: str(game_version), 9: 3, 10: 1, 11: "03626253513637754174"},
            19: 329, 21: bytes.fromhex("374f521955"), 24: {1: 21},
            27: "a_6534489873065906362"}}
    return create_packet(create_proto(fields).hex(), "0515", key, iv)

def team_fresh(account_id, key, iv):
    return create_packet(create_proto({1: 72, 2: {1: int(account_id)}}).hex(), "0515", key, iv)

def invite_player_in_team(target_uid, key, iv, region="IND"):
    return create_packet(create_proto({1: 2, 2: {1: int(target_uid), 2: region, 4: 1}}).hex(),
                         "0515", key, iv)

def accept_team_invite(target_uid, group_id, key, iv):
    fields = {1: 4, 2: {1: int(target_uid), 3: int(target_uid),
        4: bytes.fromhex("0107090a0b120f19202729"), 8: 1,
        9: {1: "08FBA33B0522052002041B0222220007000C00010004000547E265AE1080779546762514110104076fa2e8770e748c3f6a68ed75000000ff08080500cacfa16d",
            2: 235, 3: {14: 80, 11: 86}, 4: "{Y\\R", 6: 13, 7: {2: 4},
            8: "1.132.9", 9: 2, 10: 1, 11: "0362625351"},
        10: str(group_id),
        11: {"1": "IDC3", "2": 107, "3": "IND"}, 13: "en", 16: "374f5219",
        20: {1: 21}, 23: "a_6534489873065906362",
        24: "https://dl-sg-production.freefiremobile.com/",
        27: {1: 2, 2: 4}}}
    return create_packet(create_proto(fields).hex(), "0515", key, iv)

def start_match_team(account_id, key, iv, region="IND"):
    fields = {1: 9, 2: {1: int(account_id), 7: {1: "IDC3", 2: 410, 3: region}}}
    return create_packet(create_proto(fields).hex(), "0515", key, iv)

def ready_for_game(uid, key, iv):
    return create_packet(create_proto({1: 15, 2: {1: uid, 2: 1}}).hex(), "0519", key, iv)

def guild_apply_tcp(guild_id, key, iv):
    msg = MyMessage()
    msg.field_1 = int(guild_id)
    raw = msg.SerializeToString()
    return create_packet(raw.hex(), "0515", key, iv)


# ═══════════════════════════ MAJORLOGIN / GETLOGIN ═══════════════════════════
async def build_majorlogin_payload(open_id, access_token, platform, client_version, dev):
    try:
        p = {
            3: str(datetime.now())[:-7], 4: "free fire", 5: "1",
            7: str(client_version) if client_version else "1.132.8",
            8: str(dev.get("system_software", "Android OS 14 / API-34")),
            9: "Handheld", 10: "Telkomsel", 11: "CarrierDataNetwork",
            12: str(dev.get("screen_width", 1639)),
            13: str(dev.get("screen_height", 720)),
            14: str(dev.get("screen_dpi", 320)),
            15: str(dev.get("processor_details", "ARM64 FP ASIMD AES | 2000 | 8")),
            16: str(dev.get("memory", 5653)),
            17: str(dev.get("gpu_renderer", "Mali-G52 MC2")),
            18: "OpenGL ES 3.2 v1.r49p1-03bet0",
            19: str(dev.get("unique_device_id", f"Google|{uuid.uuid4()}")),
            20: str(dev.get("client_ip", "182.5.135.225")),
            21: "en", 22: str(open_id), 23: str(platform), 24: "Handheld",
            25: str(dev.get("model", "Xiaomi")), 26: "IND",
            29: str(access_token), 30: "1", 41: "Telkomsel", 42: "4G",
            57: "7428b253defc164018c604a1ebbfebdf", 60: "109278", 61: "55402",
            62: "868", 64: "55927", 65: "109278", 66: "55927", 67: "109278",
            73: 2,
            74: "/data/app/~~6Cw028g_ld-8Z0z2qhrOLA==/com.dts.freefireth-i3wiaEmpx8CbiRVhUMx_ag==/lib/arm64",
            76: 1,
            77: "b8e0cd5e295eee42f5860d3c86e483dd|/data/app/~~6Cw028g_ld-8Z0z2qhrOLA==/com.dts.freefireth-i3wiaEmpx8CbiRVhUMx_ag==/base.apk",
            78: 6, 79: 1, 81: "32", 83: "2019121229", 85: 3,
            86: "OpenGLES2", 87: 3071, 88: 4, 89: 14466, 93: "3rd_party",
            94: "KqsHTyb7yHjsAiyNWUUZa0DSOD6U0AhDQ76smAo1WeHHHpSmJ8KMRyRrxb2ttgJqO9YOqO/K6AORAvDMAX/qBS8+JahIkrM7kHfzlfULbgRAoZ9r",
            95: "111207", 96: "{\"cur_rate\":[60,90,120],\"support_etc2\":true}", 97: "1",
            98: "1", 99: str(platform), 100: str(platform),
            103: "1", 104: "52837", 105: "1",
            106: "https://dl.gmc.freefiremobile.com/live/ABHotUpdates/|211c933168f55902c7dfbfd8c4e2957d",
            107: "1.3fb8adbf45f44ce9",
        }
        return encrypt_api_bytes(build_proto(p))
    except Exception as e:
        print_error(f"build_majorlogin_payload: {e}"); return None

async def send_majorlogin(data, release_version, server_url):
    try:
        url = f"{server_url}MajorLogin" if server_url.endswith('/') else f"{server_url}/MajorLogin"
        hdrs = headers.copy(); hdrs["ReleaseVersion"] = str(release_version)
        r = await client.post(url, headers=hdrs, data=data)
        if r.status_code != 200:
            print_error(f"[MAJORLOGIN] HTTP {r.status_code}"); return None
        c = r.content
        if len(c) < 40: return None
        for off in [0, 64] + list(range(128)):
            try:
                m = thunderFF_pb2.MajorLoginRes(); m.ParseFromString(c[off:])
                if m.region and m.token: return m
            except Exception: continue
        return None
    except Exception as e:
        print_error(f"[MAJORLOGIN] {e}"); return None

async def send_getlogin(data, base_url, token, release_version):
    try:
        url = f"{base_url.rstrip('/')}/GetLoginData"
        hdrs = headers.copy()
        hdrs["ReleaseVersion"] = release_version
        hdrs['Authorization'] = f"Bearer {token}"
        hdrs['Host'] = "clientbp.ppmainecoonghj.com"
        r = await client.post(url, headers=hdrs, data=data)
        if r.status_code != 200: return None
        c = r.content
        rp = thunderFF_pb2.GetLoginDataRes()
        ok = False
        try:
            rp.ParseFromString(c)
            if rp.functional_addrs or rp.informational_addrs: ok = True
        except Exception: pass
        if not ok:
            for off in range(min(128, len(c))):
                try:
                    cand = thunderFF_pb2.GetLoginDataRes(); cand.ParseFromString(c[off:])
                    if cand.functional_addrs or cand.informational_addrs:
                        rp = cand; break
                except Exception: continue
        dd = {}
        try:
            parsed = Parser().parse(c.hex())
            dd = await parse_results(parsed)
        except Exception: pass
        return rp, dd
    except Exception: return None


# ═══════════════════════════ TCP STARTUP ═══════════════════════════
async def build_tcp_startup_packet(account_id, token, server_time, key, iv, region="IND", typ='OnLine'):
    uid_hex = f"{int(account_id):016x}"
    ts_hex = f"{int(server_time):08x}"
    enc = (await aes_encrypt(token.encode(), key, iv)).hex()
    enc_len = f"{len(enc)//2:08x}"
    reg = str(region).upper() if region else "IND"
    if typ == 'OnLine':
        pfx = '7114' if reg == 'IND' else ('7119' if reg == 'ID' else '7115')
        return f"{pfx}{uid_hex}{ts_hex}00000000{enc_len}{enc}"
    pfx = '9214' if reg == 'IND' else ('9219' if reg == 'ID' else '9215')
    return f"{pfx}{uid_hex}{ts_hex}{enc_len}{enc}"

async def send_keep_alive(region="IND"):
    try:
        reg = str(region).upper() if region else "IND"
        return bytes.fromhex("0214" if reg == "IND" else ("0219" if reg == "ID" else "0215"))
    except Exception:
        return bytes.fromhex("0214")


# ═══════════════════════════ UDP HELPERS ═══════════════════════════
async def has_ssan_zig(n):
    z = (n << 1) & 0xFFFFFFFFFFFFFFFF
    out = bytearray()
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
        s = (s + _DELTA) & 0xFFFFFFFF
        v0 = (v0 + (((((v1<<4)&0xFFFFFFFF)+k0)&0xFFFFFFFF ^ ((v1+s)&0xFFFFFFFF) ^ (((v1>>5)+k1)&0xFFFFFFFF)))) & 0xFFFFFFFF
        v1 = (v1 + (((((v0<<4)&0xFFFFFFFF)+k2)&0xFFFFFFFF ^ ((v0+s)&0xFFFFFFFF) ^ (((v0>>5)+k3)&0xFFFFFFFF)))) & 0xFFFFFFFF
    return v0, v1

async def tea_dec(v0, v1, k0, k1, k2, k3):
    s = (_DELTA * _ROUNDS) & 0xFFFFFFFF
    for _ in range(_ROUNDS):
        v1 = (v1 - (((((v0<<4)&0xFFFFFFFF)+k2)&0xFFFFFFFF ^ ((v0+s)&0xFFFFFFFF) ^ (((v0>>5)+k3)&0xFFFFFFFF)))) & 0xFFFFFFFF
        v0 = (v0 - (((((v1<<4)&0xFFFFFFFF)+k0)&0xFFFFFFFF ^ ((v1+s)&0xFFFFFFFF) ^ (((v1>>5)+k1)&0xFFFFFFFF)))) & 0xFFFFFFFF
        s = (s - _DELTA) & 0xFFFFFFFF
    return v0, v1

async def tea_cbc_encrypt(padded, key_bytes):
    k0,k1,k2,k3 = (struct.unpack_from("<I", key_bytes, o)[0] for o in (0,4,8,12))
    out = bytearray(len(padded)); pc = bytearray(8); pi = bytearray(8)
    for i in range(0, len(padded), 8):
        x = bytearray(8)
        for j in range(8): x[j] = padded[i+j] ^ pc[j]
        e0,e1 = await tea_enc(struct.unpack_from("<I", x, 0)[0],
                              struct.unpack_from("<I", x, 4)[0], k0,k1,k2,k3)
        enc = bytearray(8)
        struct.pack_into("<I", enc, 0, e0); struct.pack_into("<I", enc, 4, e1)
        for j in range(8): out[i+j] = enc[j] ^ pi[j]
        pc[:] = out[i:i+8]; pi[:] = x
    return bytes(out)

async def tea_cbc_decrypt(body, key_bytes):
    k0,k1,k2,k3 = (struct.unpack_from("<I", key_bytes, o)[0] for o in (0,4,8,12))
    out = bytearray(len(body)); pi = bytearray(8); pc = bytearray(8)
    x = bytearray(8); dec = bytearray(8)
    for i in range(0, len(body), 8):
        for j in range(8): x[j] = body[i+j] ^ pi[j]
        d0,d1 = await tea_dec(struct.unpack_from("<I", x, 0)[0],
                              struct.unpack_from("<I", x, 4)[0], k0,k1,k2,k3)
        struct.pack_into("<I", dec, 0, d0); struct.pack_into("<I", dec, 4, d1)
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
        else:
            v = ((val & 0xFFFF) ^ v80) & 0xFFFF
            out.append(v & 0xFF); out.append((v >> 8) & 0xFF)
    return bytes(out)

async def crc7_buff(crc, buf):
    c = crc & 0x7F
    for b in buf: c = CRC7_TABLE[((2*(c & 0xFF)) ^ (b & 0xFF)) & 0xFF] & 0x7F
    return c & 0x7F

async def sv_frame(msg_key, layout, so, cmd, oid, flags, content, key, encrypted=True):
    k = key[0]; v80 = ((k << 8) | k) & 0xFFFF
    body = await tea_cbc_encrypt(await build_padded(content), key) if encrypted else content
    hdr = bytearray([msg_key, 0]) + await encode_header(layout, so, cmd, oid, flags, len(body), k, v80)
    pkt = bytearray(hdr + body)
    pkt[1] = await crc7_buff(0, bytes(pkt[2:])) & 0x7F
    return bytes(pkt)

async def build_packet(msg_key, layout, so, cmd, oid, flags, content, key, encrypted=True):
    k = key[0]; v80 = ((k << 8) | k) & 0xFFFF
    body = await tea_cbc_encrypt(await build_padded(content), key) if encrypted else content
    hdr = bytearray([msg_key, 0])
    for code in layout:
        val = {0:so, 1:cmd, 2:oid, 3:flags, 4:len(body)}[code]
        if _FIELD_SIZES[code] == 1: hdr.append((val & 0xFF) ^ k)
        else:
            v = ((val & 0xFFFF) ^ v80) & 0xFFFF
            hdr.append(v & 0xFF); hdr.append((v >> 8) & 0xFF)
    pkt = bytearray(hdr + body)
    pkt[1] = await crc7_buff(0, bytes(pkt[2:])) & 0x7F
    return bytes(pkt)

async def layouts_from_mask(mask):
    ru = [int(c) for c in str(mask).strip()]
    nr = [c for c in ru if c != 2]
    return ru, nr

async def build_hello_packet(text, key, layout):
    data = text.encode("utf-8")
    if len(data) > 25: raise ValueError("too long")
    content = b"\x10\x00\x00\x00" + data + b"\x00" * (29 - 4 - len(data))
    k = key[0] if key else 10
    v80 = ((k << 8) | k) & 0xFFFF
    layout = [int(c) for c in str(layout).strip()] if isinstance(layout, str) else list(layout)
    padded = await build_padded(content)
    enc_body = await tea_cbc_encrypt(padded, key)
    hdr = await encode_header(layout, 1, 1, 0, 1, len(enc_body), k, v80)
    pkt = bytearray([0x63, 0x00]) + hdr + enc_body
    pkt[1] = await crc7_buff(0, pkt[2:]) & 0x7F
    return bytes(pkt).hex()

async def classify(frame):
    cmd = frame["cmd"]
    name = MESSAGE_ID_TO_NAME.get(cmd, f"UNKNOWN_{cmd}")
    if name == "UDP_HELLO": return "HELLO"
    if name == "UDP_ACK": return "ACK"
    if name == "UDP_PING": return "PING"
    if name == "RUDP_JOIN_MATCH": return "JOIN_MATCH"
    if name.startswith("RUDP_"): return name
    if name.startswith("UDP_"): return name
    return "DATA"

async def reply_for(frame, key, mask, ack_key=0x68, ping_key=0x6D, hello_key=0x5B, ack_style="short"):
    _, nr = await layouts_from_mask(mask)
    typ = await classify(frame)
    if typ == "HELLO":
        if ack_style == "echo":
            content = frame["content"] if frame["content"] else b"\x10\x00\x00\x00"
            return typ, await build_packet(hello_key, nr, 1, 1, None, 1, content, key)
        return typ, await build_packet(ack_key, nr, 0, 2, None, 1, b"\x01\x00", key)
    if typ == "ACK":
        content = frame["content"] if frame["content"] else b"\x01\x00"
        return typ, await build_packet(ack_key, nr, 0, 2, None, 1, content, key)
    if typ == "PING":
        c = frame["content"]
        counter = c[:4] if len(c) >= 4 else c
        return typ, await build_packet(ping_key, nr, 0, 3, None, 0, counter + b"\x00\x00\x00", key, encrypted=False)
    if typ == "JOIN_MATCH":
        return typ, await build_packet(ack_key, nr, 0, 2, None, 1, b"\x02\x00", key)
    return typ, None

async def keepalive_ping(sock, ip, port, key_bytes, mask, stop_event):
    nr = (await layouts_from_mask(mask))[1]
    ping_keys = [0x66, 0x6D, 0x69, 0x6C, 0x6B, 0x6E, 0x6F, 0x70]
    loop = asyncio.get_event_loop(); i = 0
    while not stop_event.is_set():
        pk = ping_keys[i % len(ping_keys)]
        counter = int(time.time() * 1000) & 0xFFFFFFFF
        pkt = await build_packet(pk, nr, 0, 3, None, 0, struct.pack("<I", counter) + b"\x00\x00\x00",
                                 key_bytes, encrypted=False)
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
        out[_FIELD_NAMES[code]] = ((buf[off] ^ k) if size == 1
                                    else ((buf[off] | (buf[off+1] << 8)) ^ v80) & 0xFFFF)
        off += size
    out["headerLen"] = off
    return out

async def oicq_unpad(padded):
    if not padded or len(padded) < 8: return None
    if not all(padded[-1-i] == 0 for i in range(7)): return None
    pad_len = padded[0] & 0x07
    s = 3 + pad_len; e = len(padded) - 7
    return padded[s:e] if s < e else b""

async def decode_packet(packet, key, mask=None):
    data = bytes(packet) if isinstance(packet, bytes) else bytes.fromhex(packet)
    if len(data) < 8: return None
    k = key[0]; v80 = ((k << 8) | k) & 0xFFFF
    crc_ok = (data[1] & 0x7F) == await crc7_buff(0, data[2:])
    candidates = []
    if mask:
        ru, nr = await layouts_from_mask(mask)
        layouts = [("RUDP", ru), ("nonRUDP", nr)]
    else:
        layouts = [("RUDP", list(p)) for p in itertools.permutations([0,1,2,3,4])]
        layouts += [("nonRUDP", list(p)) for p in itertools.permutations([0,1,3,4])]
    for kind, layout in layouts:
        f = await try_header(data, layout, k, v80)
        if not f: continue
        if f["flags"] > 7 or f["sendOption"] > 7: continue
        if f["length"] != len(data) - f["headerLen"]: continue
        body = data[f["headerLen"]:f["headerLen"]+f["length"]]
        content = None
        if f["flags"] & 1:
            if len(body) < 8 or len(body) % 8 != 0: continue
            padded = await tea_cbc_decrypt(body, key)
            content = await oicq_unpad(padded)
            if content is None: continue
        else: content = body
        score = (1 if crc_ok else 0) + (1 if content is not None else 0)
        candidates.append({"kind":kind, "layout":layout, "headerLen":f["headerLen"],
            "msgKey":data[0], "cmd":f["cmd"], "flags":f["flags"],
            "sendOption":f["sendOption"], "orderId":f.get("orderId"),
            "length":f["length"], "content":content, "crcOk":crc_ok,
            "score":score, "total":len(data)})
    if not candidates: return None
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[0]

async def build_match_startup_packets(token, udp_key, match_code, account_id, block_val,
                                      server_ip="", region="IND", client_version="1.132.6",
                                      client_version_code="2019121229", access_token="",
                                      mode_id=BR_MODE_ID, map_id=BR_MAP_ID):
    token = token.strip()
    udp_key = bytes.fromhex(udp_key)
    match_code = [int(ch) for ch in str(match_code).strip()]
    thunder_jwt = token[:660] if len(token) > 660 else token
    sharma_jwt = token[660:] if len(token) > 660 else ""
    eth = thunder_jwt.encode() if isinstance(thunder_jwt, str) else thunder_jwt
    esh = sharma_jwt.encode() if isinstance(sharma_jwt, str) else sharma_jwt
    garena420 = await has_ssan_zig(len(eth)) + eth
    reg = str(region).upper() if region else "IND"
    csoversea_block = bytes.fromhex(
        "ca0163736f7665727365612e7374726f6e67686f6c642e66726565666972656d6f62696c652e636f6d"
        "3b302e302e302e303b33342e3132362e37362e34353b33342e38372e3137372e31343b33342e38372e"
        "3137302e3233303b33352e3138352e3138332e35370000000000000100000000000000000000000001"
        "00000800000100000000000100a8a2d7bebd8d8bdf110200")
    mid = bytes.fromhex('0000000001000102030101') + await has_ssan_zig(len(reg)) + reg.encode()
    mid += bytes.fromhex('0001030003000004')
    mid += await has_ssan_zig(len(client_version)) + client_version.encode()
    mid += await has_ssan_zig(len(client_version_code)) + client_version_code.encode()
    mid += csoversea_block
    clean_ip = server_ip.split(':')[0] if server_ip else "0.0.0.0"
    mid += await has_ssan_zig(len(clean_ip)) + clean_ip.encode()
    if access_token:
        clean_acc = access_token.strip()
        mid += await has_ssan_zig(len(clean_acc)) + clean_acc.encode()
    mid += await has_ssan_zig(len(esh)) + esh
    tg = (await uleb_encode(int(account_id)) + await uleb_encode(int(block_val)) +
          await uleb_encode(1) + await uleb_encode(int(mode_id)) +
          await uleb_encode(int(block_val)) + await uleb_encode(int(map_id)) + mid)
    process = await sv_frame(0x5E, match_code, 2, 447, 0, 1, garena420, udp_key)
    loading = await sv_frame(0x5A, match_code, 2, 448, 1, 1, tg, udp_key)
    return process.hex(), loading.hex()


# ═══════════════════════════ MOVEMENT ═══════════════════════════
async def build_movement_packet_2001(key_bytes, msg_key, player_state, x, y, z,
                                     tick, counter, move_state, account_uid,
                                     room_code, phase="game"):
    if phase == "game":
        TAIL = (b"\x00"*7 + b"\x93\xca\xd5\xf9\x0b" + b"\x8e\xfe\xfc\xf7\x0b"
                + b"\xf4\xe0\xfe\xf7\x03" + b"\x00\x00")
    else:
        TAIL = (b"\x00"*7 + b"\xbd\xb6\xe1\xf3\x03" + b"\x00"
                + b"\xc4\xb6\xe1\xfb\x0b" + b"\x00\x00")
    body = bytearray()
    body += await uleb_encode(int(account_uid))
