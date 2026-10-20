# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════════════
#  🇧🇩  TCP BZ — PREMIUM HEX DECODER  🇧🇩
#  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#     👑 Owner      : TCP BZ
#     🌏 Country    : Bangladesh 🇧🇩
#     🔧 Purpose    : Hex / Protobuf / JSON Multi-Decoder
#     ⚡ Version    : PREMIUM EDITION v2.0
#     📅 Build      : 2026
#  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  © 2026 TCP BZ — All Rights Reserved
# ═══════════════════════════════════════════════════════════════════

import re
import json
import base64
import sys
import os

# ═══════════════════════════ BRAND ═══════════════════════════
BRAND_NAME       = "TCP bz"
BRAND_COUNTRY    = "Bangladesh 🇧🇩"
BRAND_VERSION    = "PREMIUM v2.0"
BRAND_YEAR       = "2026"
BRAND_TAGLINE    = "🔥 Bangladesh's #1 Decoder 🔥"

# Windows terminal UTF-8 fix
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ═══════════════════════════ COLORS ═══════════════════════════
class C:
    BRAND    = "\033[38;5;208m"   # Orange
    BDRED    = "\033[38;5;196m"   # BD Red
    BDGREEN  = "\033[38;5;46m"    # BD Green
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
{C.GOLD}          ⚡  {C.BOLD}PREMIUM HEX / PROTOBUF DECODER{C.ENDC} {C.GOLD}⚡{C.ENDC}
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

# ═══════════════════════════ HEX DATA ═══════════════════════════
HEX_DATA = """
08d5a4adaf0b121fd2a8e1b49ce1b487e1b487eaa4aaeaa4a8eaa4aaeaa4aaeaa4a8eaa4aa4e2e188ab3bcd10620fae8d4b81528043023381f4801620857656c636f6d65216a03494e44720e7b2274616773223a205b31345d7d7a025b5da001dfd403b801ba95d2b80988020da002fcf401a802b236b00204b80292af0cc802e907e002b5a7b2d506e80201fa02008a0300
"""


def decode_varint(data, pos):
    """Decode a Protocol Buffers-style varint."""
    value = 0
    shift = 0

    while pos < len(data):
        byte = data[pos]
        pos += 1

        value |= (byte & 0x7F) << shift

        if not (byte & 0x80):
            return value, pos

        shift += 7

        if shift >= 70:
            raise ValueError("Varint is too large")

    raise ValueError("Incomplete varint")


def extract_strings(data):
    """Extract printable ASCII strings from binary data."""
    text = data.decode("utf-8", errors="replace")
    strings = re.findall(r"[\x20-\x7E]{3,}", text)
    return strings


def decode_hex(hex_string):
    # ─── Input Validation ───
    hex_string = re.sub(r"\s+", "", hex_string)

    if not hex_string:
        err("Hex input is empty")
        return

    if not re.fullmatch(r"[0-9a-fA-F]+", hex_string):
        err("Input contains invalid hexadecimal characters")
        return

    if len(hex_string) % 2:
        err("Hex input must contain an even number of digits")
        return

    data = bytes.fromhex(hex_string)

    # ─── Premium Header ───
    print_banner()
    section(f"🔍 DECODER — {len(data)} BYTES", C.BDRED)
    info(f"Input size  : {C.BOLD}{len(data)}{C.ENDC} bytes")
    info(f"Owner       : {C.BOLD}{BRAND_NAME}{C.ENDC}")
    info(f"Country     : {C.BOLD}{BRAND_COUNTRY}{C.ENDC}")

    # ─── [1] HEX ───
    section("[1] 📦 HEX OUTPUT", C.SKY)
    print(f"{C.SKY}{data.hex()}{C.ENDC}")

    # ─── [2] UTF-8 Text ───
    section("[2] 📝 UTF-8 TEXT", C.SKY)
    utf8_text = data.decode("utf-8", errors="replace")
    print(f"{C.WHITE}{utf8_text}{C.ENDC}")

    # ─── [3] Extracted Strings ───
    section("[3] 🔤 EXTRACTED STRINGS", C.PURPLE)
    strings = extract_strings(data)
    if strings:
        for i, item in enumerate(strings, 1):
            print(f"  {C.GOLD}{i:>2}.{C.ENDC} {C.WHITE}{repr(item)}{C.ENDC}")
    else:
        warn("No printable strings found")

    # ─── [4] Raw Bytes ───
    section("[4] 🧊 RAW BYTES", C.PURPLE)
    print(f"{C.DIM}{data}{C.ENDC}")

    # ─── [5] Base64 ───
    section("[5] 🔐 BASE64", C.PINK)
    b64 = base64.b64encode(data).decode("ascii")
    print(f"{C.PINK}{b64}{C.ENDC}")

    # ─── [6] JSON Detection ───
    section("[6] 🧩 JSON DETECTION", C.BDGREEN)
    found_json = False

    for item in strings:
        try:
            parsed = json.loads(item)
            print(f"{C.BDGREEN}  ✔ Valid JSON found:{C.ENDC}")
            print(f"{C.WHITE}{json.dumps(parsed, indent=2, ensure_ascii=False)}{C.ENDC}")
            found_json = True
        except json.JSONDecodeError:
            continue

    if not found_json:
        warn("No standalone JSON string detected.")

    # ─── [7] Protobuf Wire Scan ───
    section("[7] 🧬 PROTOBUF WIRE SCAN", C.GOLD)
    pos = 0
    field_count = 0

    try:
        while pos < len(data):
            start = pos
            key, pos = decode_varint(data, pos)

            field_number = key >> 3
            wire_type = key & 7

            if field_number == 0:
                err(f"Invalid field key at offset {start}")
                break

            if wire_type == 0:
                value, pos = decode_varint(data, pos)
                print(
                    f"  {C.SKY}offset={start:>4}{C.ENDC} | "
                    f"{C.GOLD}field={field_number:>3}{C.ENDC} | "
                    f"{C.PURPLE}wire_type=0{C.ENDC} | "
                    f"{C.BDGREEN}varint={value}{C.ENDC}"
                )
                field_count += 1

            elif wire_type == 1:
                if pos + 8 > len(data):
                    raise ValueError("Incomplete 64-bit field")

                value = data[pos:pos + 8]
                pos += 8

                print(
                    f"  {C.SKY}offset={start:>4}{C.ENDC} | "
                    f"{C.GOLD}field={field_number:>3}{C.ENDC} | "
                    f"{C.PURPLE}wire_type=1{C.ENDC} | "
                    f"{C.WHITE}hex={value.hex()}{C.ENDC}"
                )
                field_count += 1

            elif wire_type == 2:
                length, pos = decode_varint(data, pos)

                if pos + length > len(data):
                    raise ValueError("Length-delimited field exceeds data")

                value = data[pos:pos + length]
                pos += length

                text_repr = value.decode("utf-8", errors="replace")
                print(
                    f"  {C.SKY}offset={start:>4}{C.ENDC} | "
                    f"{C.GOLD}field={field_number:>3}{C.ENDC} | "
                    f"{C.PURPLE}wire_type=2{C.ENDC} | "
                    f"{C.WHITE}len={length:<3}{C.ENDC} | "
                    f"{C.BDGREEN}text={text_repr!r}{C.ENDC}"
                )
                field_count += 1

            elif wire_type == 5:
                if pos + 4 > len(data):
                    raise ValueError("Incomplete 32-bit field")

                value = data[pos:pos + 4]
                pos += 4

                print(
                    f"  {C.SKY}offset={start:>4}{C.ENDC} | "
                    f"{C.GOLD}field={field_number:>3}{C.ENDC} | "
                    f"{C.PURPLE}wire_type=5{C.ENDC} | "
                    f"{C.WHITE}hex={value.hex()}{C.ENDC}"
                )
                field_count += 1

            else:
                raise ValueError(f"Unsupported wire type {wire_type}")

    except ValueError as exc:
        warn(f"Wire scan stopped: {exc}")
        info("The data may not be a standalone Protobuf message.")

    # ─── Footer ───
    section("✅ DECODING FINISHED", C.BDGREEN)
    ok(f"Total fields scanned : {C.BOLD}{field_count}{C.ENDC}")
    ok(f"Owner                : {C.BOLD}{BRAND_NAME}{C.ENDC}")
    ok(f"Country              : {C.BOLD}{BRAND_COUNTRY}{C.ENDC}")
    print()
    print(f"{C.BDRED}  © {BRAND_YEAR} {BRAND_NAME} — All Rights Reserved{C.ENDC}")
    print(f"{C.BDGREEN}  🇧🇩 Made in Bangladesh{C.ENDC}")
    print(f"{C.DIM}  {'─' * 60}{C.ENDC}\n")


# ═══════════════════════════ MAIN ═══════════════════════════
if __name__ == "__main__":
    # Command-line support: python file.py <hex>
    if len(sys.argv) > 1:
        user_hex = " ".join(sys.argv[1:])
        decode_hex(user_hex)
    else:
        decode_hex(HEX_DATA)