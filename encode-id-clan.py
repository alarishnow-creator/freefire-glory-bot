# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════════════
#  🇧🇩  TCP BZ — PREMIUM CLAN ENCRYPTOR  🇧🇩
#  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#     👑 Owner      : TCP BZ
#     🌏 Country    : Bangladesh 🇧🇩
#     🔧 Purpose    : AES-CBC Protobuf Clan ID Encryptor
#     ⚡ Version    : PREMIUM EDITION v2.0
#     📅 Build      : 2026
#  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  © 2026 TCP BZ — All Rights Reserved
# ═══════════════════════════════════════════════════════════════════

import sys
import json
import time
import binascii
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder

# ─── Windows terminal UTF-8 fix ───
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ═══════════════════════════ BRAND ═══════════════════════════
BRAND_NAME       = "TCP BZ"
BRAND_COUNTRY    = "Bangladesh 🇧🇩"
BRAND_VERSION    = "PREMIUM v2.0"
BRAND_YEAR       = "2026"
BRAND_TAGLINE    = "🔥 Bangladesh's #1 Encryptor 🔥"

# ═══════════════════════════ COLORS ═══════════════════════════
class C:
    BRAND    = "\033[38;5;208m"
    BDRED    = "\033[38;5;196m"
    BDGREEN  = "\033[38;5;46m"
    GOLD     = "\033[38;5;220m"
    PURPLE   = "\033[38;5;93m"
    PINK     = "\033[38;5;213m"
    SKY      = "\033[38;5;51m"
    WHITE    = "\033[97m"
    DIM      = "\033[2m"
    BOLD     = "\033[1m"
    ENDC     = "\033[0m"

def clr(text, color):
    return f"{color}{text}{C.ENDC}"

def print_banner():
    banner = f"""
{C.BDRED}╔══════════════════════════════════════════════════════════════════╗
{C.BDRED}║{C.BDGREEN}  ██████╗  █████╗ ███████╗██╗███╗   ██╗    ████████╗██╗  ██╗████████╗{C.BDRED} ║
{C.BDRED}║{C.BDGREEN}  ██╔══██╗██╔══██╗██╔════╝██║████╗  ██║    ╚══██╔══╝╚██╗██╔╝╚══██╔══╝{C.BDRED} ║
{C.BDRED}║{C.BDGREEN}  ██████╔╝███████║█████╗  ██║██╔██╗ ██║       ██║    ╚███╔╝    ██║   {C.BDRED} ║
{C.BDRED}║{C.BDGREEN}  ██╔══██╗██╔══██║██╔══╝  ██║██║╚██╗██║       ██║    ██╔██╗    ██║   {C.BDRED} ║
{C.BDRED}║{C.BDGREEN}  ██║  ██║██║  ██║██║     ██║██║ ╚████║       ██║   ██╔╝ ██╗   ██║   {C.BDRED} ║
{C.BDRED}║{C.BDGREEN}  ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝  ╚═══╝       ╚═╝   ╚═╝  ╚═╝   ╚═╝   {C.BDRED} ║
{C.BDRED}╚══════════════════════════════════════════════════════════════════╝{C.ENDC}
{C.GOLD}          ⚡  {C.BOLD}PREMIUM CLAN ENCRYPTOR — AES-CBC{C.ENDC} {C.GOLD}⚡{C.ENDC}
{C.BDGREEN}          🇧🇩  Made in {BRAND_COUNTRY}  |  © {BRAND_YEAR} {BRAND_NAME}  🇧🇩{C.ENDC}
{C.PINK}              {BRAND_TAGLINE}{C.ENDC}
{C.DIM}      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.ENDC}
"""
    print(banner)

def section(title, color=None):
    color = color or C.PURPLE
    bar = "━" * 60
    print(f"\n{color}┏{bar}┓{C.ENDC}")
    print(f"{color}┃{C.ENDC}  {C.BOLD}{C.GOLD}{title.center(56)}{C.ENDC}  {color}┃{C.ENDC}")
    print(f"{color}┗{bar}┛{C.ENDC}")

def ok(msg):
    print(f"  {C.BDGREEN}✔{C.ENDC} {C.WHITE}[{C.BDGREEN}✓{C.WHITE}]{C.ENDC} {msg}")

def err(msg):
    print(f"  {C.BDRED}✘{C.ENDC} {C.WHITE}[{C.BDRED}!{C.WHITE}]{C.ENDC} {msg}")

def warn(msg):
    print(f"  {C.GOLD}⚠{C.ENDC} {C.WHITE}[{C.GOLD}W{C.WHITE}]{C.ENDC} {msg}")

def info(msg):
    print(f"  {C.SKY}ℹ{C.ENDC} {C.WHITE}[{C.SKY}i{C.WHITE}]{C.ENDC} {msg}")

# ═══════════════════════════ CONFIG ═══════════════════════════
AES_KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
AES_IV  = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

# ═══════════════════════════ PROTOBUF SCHEMA ═══════════════════════════
_sym_db = _symbol_database.Default()
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(
    b'\n\ndata.proto"(\n\x06MyData\x12\x0e\n\x06\x66ield1\x18\x01 \x01(\r\x12\x0e\n\x06\x66ield2\x18\x02 \x01(\rb\x06proto3'
)
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'data_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
    DESCRIPTOR._options = None
    _globals['_MYDATA']._serialized_start = 14
    _globals['_MYDATA']._serialized_end = 54
MyData = _sym_db.GetSymbol('MyData')


# ═══════════════════════════ CORE FUNCTIONS ═══════════════════════════
def build_proto(clan_id: int, field2: int = 1) -> bytes:
    """Build MyData protobuf message."""
    my_data = MyData()
    my_data.field1 = int(clan_id)
    my_data.field2 = int(field2)
    return my_data.SerializeToString()


def encrypt_clan_id(clan_id: int, field2: int = 1) -> dict:
    """Encrypt clan_id with AES-CBC."""
    data_dict = {"1": int(clan_id), "2": int(field2)}

    my_data = MyData()
    my_data.field1 = data_dict["1"]
    my_data.field2 = data_dict["2"]
    data_bytes = my_data.SerializeToString()

    padded_data = pad(data_bytes, AES.block_size)
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    encrypted_data = cipher.encrypt(padded_data)

    hex_formatted = " ".join([f"{byte:02X}" for byte in encrypted_data])
    hex_compact = encrypted_data.hex()
    b64 = binascii.b2a_base64(encrypted_data).decode().strip()

    return {
        "clan_id":       int(clan_id),
        "field2":        int(field2),
        "plain_bytes":   data_bytes,
        "plain_hex":     data_bytes.hex(),
        "plain_size":    len(data_bytes),
        "padded_size":   len(padded_data),
        "encrypted":     encrypted_data,
        "encrypted_hex": hex_compact,
        "hex_formatted": hex_formatted,
        "base64":        b64,
    }


def print_result(result: dict):
    """Print the encryption result in premium format."""
    section(f"🔐 ENCRYPTED — CLAN {result['clan_id']}", C.BDGREEN)

    info(f"Clan ID        : {C.BOLD}{result['clan_id']}{C.ENDC}")
    info(f"Field 2        : {C.BOLD}{result['field2']}{C.ENDC}")
    info(f"Plain bytes    : {C.BOLD}{result['plain_size']}{C.ENDC}")
    info(f"Padded bytes   : {C.BOLD}{result['padded_size']}{C.ENDC}")

    # Plain Protobuf
    section("📦 PLAIN PROTOBUF (HEX)", C.SKY)
    print(f"{C.SKY}{result['plain_hex']}{C.ENDC}")

    # Encrypted Hex (Formatted)
    section("✨ ENCRYPTED HEX (SPACED FORMAT)", C.GOLD)
    print(f"{C.GOLD}{result['hex_formatted']}{C.ENDC}")

    # Encrypted Hex (Compact)
    section("🧬 ENCRYPTED HEX (COMPACT)", C.PURPLE)
    print(f"{C.PURPLE}{result['encrypted_hex']}{C.ENDC}")

    # Base64
    section("🔐 BASE64 ENCODED", C.PINK)
    print(f"{C.PINK}{result['base64']}{C.ENDC}")

    # Copy-friendly single-line
    section("📋 COPY-PASTE READY", C.BDGREEN)
    print(f"{C.WHITE}{result['hex_formatted']}{C.ENDC}")

    # Footer
    section("✅ ENCRYPTION COMPLETE", C.BDGREEN)
    ok(f"Owner    : {C.BOLD}{BRAND_NAME}{C.ENDC}")
    ok(f"Country  : {C.BOLD}{BRAND_COUNTRY}{C.ENDC}")
    ok(f"Cipher   : {C.BOLD}AES-128-CBC + PKCS7 Padding{C.ENDC}")
    print()
    print(f"{C.BDRED}  © {BRAND_YEAR} {BRAND_NAME} — All Rights Reserved{C.ENDC}")
    print(f"{C.BDGREEN}  🇧🇩 Made in Bangladesh{C.ENDC}")
    print(f"{C.DIM}  {'─' * 60}{C.ENDC}\n")


# ═══════════════════════════ MAIN ═══════════════════════════
def main():
    print_banner()

    # ─── Input ───
    if len(sys.argv) > 1:
        try:
            clan_id = int(sys.argv[1])
            field2 = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        except ValueError:
            err("Invalid clan ID — must be an integer")
            sys.exit(1)
        info(f"Input from CLI   : Clan ID = {clan_id}, Field2 = {field2}")
    else:
        # Default clan ID
        clan_id = 3034881538
        field2 = 1
        info(f"Using default    : Clan ID = {clan_id}, Field2 = {field2}")

    section("🎯 INPUT PARAMETERS", C.SKY)
    info(f"Clan ID    : {C.BOLD}{clan_id}{C.ENDC}")
    info(f"Field 2    : {C.BOLD}{field2}{C.ENDC}")
    info(f"Key (hex)  : {C.DIM}{AES_KEY.hex()}{C.ENDC}")
    info(f"IV  (hex)  : {C.DIM}{AES_IV.hex()}{C.ENDC}")

    # ─── Encrypt ───
    try:
        result = encrypt_clan_id(clan_id, field2)
    except Exception as e:
        err(f"Encryption failed: {e}")
        sys.exit(1)

    # ─── Output ───
    print_result(result)


# ═══════════════════════════ ENTRY ═══════════════════════════
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        warn("Interrupted by user.")
    except Exception as e:
        err(f"Fatal error: {e}")
        sys.exit(1)