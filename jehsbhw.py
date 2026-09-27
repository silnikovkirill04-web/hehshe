#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KiriillBR Playerok Bot v10.1 — мультиинстанс + автообновление."""
import json, logging, os, re, sys, threading, time, urllib.request, subprocess
from datetime import datetime
from logging.handlers import RotatingFileHandler
import telebot
from telebot.types import InlineKeyboardMarkup as K, InlineKeyboardButton as B

BOT_VERSION = "10.1"

# ═══════════════════ МУЛЬТИИНСТАНС ═══════════════════
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_FILE = os.path.join(BASE_DIR, ".instance")

def get_instance():
    env = os.environ.get("INSTANCE")
    if env: return env
    if os.path.exists(INSTANCE_FILE):
        try:
            with open(INSTANCE_FILE, encoding="utf-8") as f:
                n = f.read().strip()
            if n: return n
        except Exception: pass
    return None

def set_instance(nick):
    nick = re.sub(r"[^A-Za-z0-9_\-]", "_", str(nick))[:32]
    if not nick: raise ValueError("Пустой ник")
    with open(INSTANCE_FILE, "w", encoding="utf-8") as f: f.write(nick)
    os.makedirs(os.path.join(BASE_DIR, nick), exist_ok=True)
    return nick

def instance_dir():
    n = get_instance()
    return os.path.join(BASE_DIR, n) if n else BASE_DIR

INST_DIR = instance_dir()
os.makedirs(INST_DIR, exist_ok=True)

CONFIG_FILE   = os.path.join(INST_DIR, "config.json")
CREDS_FILE    = os.path.join(INST_DIR, "creds.json")
SETTINGS_FILE = os.path.join(INST_DIR, "settings.json")
DEALS_FILE    = os.path.join(INST_DIR, "deals.json")
USERS_FILE    = os.path.join(INST_DIR, "users.json")
AI_FILE       = os.path.join(INST_DIR, "ai_config.json")
NAMES_FILE    = os.path.join(INST_DIR, "chatnames.json")
PLUGINS_FILE  = os.path.join(INST_DIR, "plugins.json")
PLUGINS_DIR   = os.path.join(INST_DIR, "plugins")
SEEN_FILE     = os.path.join(INST_DIR, "seen.json")
LOG_FILE      = os.path.join(INST_DIR, "bot.log")
os.makedirs(PLUGINS_DIR, exist_ok=True)

# ═══════════════════ ЛОГИ ═══════════════════
def setup_logging():
    root = logging.getLogger(); root.setLevel(logging.DEBUG)
    for h in list(root.handlers): root.removeHandler(h)
    fmt = logging.Formatter("%(asctime)s,%(msecs)03d [%(levelname)-5s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    ch = logging.StreamHandler(sys.stdout); ch.setLevel(logging.INFO); ch.setFormatter(fmt); root.addHandler(ch)
    try:
        fh = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=5, encoding="utf-8")
        fh.setLevel(logging.DEBUG); fh.setFormatter(fmt); root.addHandler(fh)
    except Exception as e: print("log:", e)
    for n in ("urllib3","requests","curl_cffi","telebot","playerokapi","charset_normalizer"):
        logging.getLogger(n).setLevel(logging.WARNING)

setup_logging()
L = logging.getLogger("Bot")

# ═══════════════════ JSON ═══════════════════
def jload(p, d):
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except Exception: return d

def jsave(p, d):
    try:
        with open(p + ".tmp", "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2, default=str)
        os.replace(p + ".tmp", p)
    except Exception as e: L.error("save %s: %s", p, e)

def save_config(c): jsave(CONFIG_FILE, c)

# ═══════════════════ ВИЗАРД ═══════════════════
def setup_wizard():
    global INST_DIR, CONFIG_FILE
    print("=" * 60); print("  Первый запуск KiriillBR Playerok Bot"); print("=" * 60); print()
    while True:
        nick = input("Придумай ник для бота (латиница/цифры/_-): ").strip()
        if not nick: print("Пустой — ещё раз"); continue
        try: nick = set_instance(nick); break
        except Exception as e: print("Ошибка:", e)
    INST_DIR = instance_dir()
    CONFIG_FILE = os.path.join(INST_DIR, "config.json")
    print(); print("📁 Инстанс:", nick); print("📁 Папка:  ", INST_DIR); print()
    cfg = {"instance": nick}
    cfg["token"] = input("1. Токен бота (от @BotFather): ").strip()
    cfg["admin_password"] = input("2. Пароль для входа: ").strip()
    try: cfg["admin_id"] = int(input("3. Твой Telegram ID (у @userinfobot): ").strip())
    except ValueError: cfg["admin_id"] = 0
    cfg["proxy"] = input("4. Прокси (SOCKS5/HTTP) [Enter=нет]: ").strip()
    cfg["github_repo"] = input("5. GitHub owner/repo [Enter=silnikovkirill04-web/hehshe]: ").strip() or "silnikovkirill04-web/hehshe"
    cfg["github_branch"] = "main"
    cfg["github_file"] = "jehsbhw.py"
    cfg["notify_messages"] = True
    cfg["notify_deals"] = True
    cfg["auto_confirm"] = False
    cfg["auto_confirm_delay"] = 30
    cfg["auto_bump"] = False
    cfg["auto_bump_min"] = 240
    cfg["auto_bump_max"] = 100
    cfg["auto_update"] = True
    cfg["tmpl"] = "Здравствуйте, {buyer}! {message}"
    save_config(cfg)
    print(); print("=" * 60); print("  ✅ Сохранено в:", CONFIG_FILE); print("=" * 60); print()
    return cfg

CFG = jload(CONFIG_FILE, {})
if not CFG.get("token") or not CFG.get("admin_password"):
    CFG = setup_wizard()

TOKEN = CFG["token"]
ADMIN_PASSWORD = CFG.get("admin_password", "")
MAIN_ADMIN = int(CFG.get("admin_id") or 0)
PROXY = CFG.get("proxy", "")
GITHUB_REPO = CFG.get("github_repo", "")
GITHUB_BRANCH = CFG.get("github_branch", "main")
GITHUB_FILE = CFG.get("github_file", "jehsbhw.py")
INSTANCE_NAME = CFG.get("instance", "default")

if PROXY:
    try:
        telebot.apihelper.proxy = {"http": PROXY, "https": PROXY}
        L.info("Telegram proxy: %s", PROXY)
    except Exception as e: L.warning("proxy: %s", e)

# ═══════════════════ ХРАНИЛИЩА ═══════════════════
CREDS = jload(CREDS_FILE, {"cookies": "", "token": "", "ddg5": ""})
SET_D = jload(SETTINGS_FILE, {
    "notify_messages": True, "notify_deals": True,
    "auto_confirm": False, "auto_confirm_delay": 30,
    "auto_bump": False, "auto_bump_min": 240, "auto_bump_max": 100,
    "auto_update": True,
    "tmpl": "Здравствуйте, {buyer}! {message}",
})
DEALS_D = jload(DEALS_FILE, {})
USERS_STATE = jload(USERS_FILE, {"authorized": []})
AI_CONFIG = jload(AI_FILE, {"enabled": False, "provider": "gemini", "api_key": "", "model": "", "strict": True})
NAMES_D = jload(NAMES_FILE, {})
PLUGS_D = jload(PLUGINS_FILE, {})
SEEN_D = jload(SEEN_FILE, {"msgs": [], "deals": []})

def save_creds(): jsave(CREDS_FILE, CREDS)
def save_set(): jsave(SETTINGS_FILE, SET_D)
def save_deals(): jsave(DEALS_FILE, DEALS_D)
def save_users(): jsave(USERS_FILE, USERS_STATE)
def save_ai(): jsave(AI_FILE, AI_CONFIG)
def save_names(): jsave(NAMES_FILE, NAMES_D)
def save_plugs(): jsave(PLUGINS_FILE, PLUGS_D)
def save_seen(): jsave(SEEN_FILE, SEEN_D)

# ═══════════════════ СЛУЖЕБНЫЕ ЧАТЫ ═══════════════════
SUPPORT_IDS = {"1f1b989c-c8ff-62c2-61ae-6f0b6ec96725": "🆘 Поддержка"}
SYSTEM_IDS  = {"1f1b989c-c8ff-62c0-0a0c-5c6c06252a37": "⚙️ Система"}

def norm(s): return "".join(c for c in str(s or "").lower() if c not in " \t\n\r-_")

def chat_name(cid):
    if cid is None: return None
    c = str(cid)
    if c in NAMES_D: return NAMES_D[c]
    n = norm(c)
    for k, v in NAMES_D.items():
        if norm(k) == n: return v
    for k, v in {**SUPPORT_IDS, **SYSTEM_IDS}.items():
        if k in c or c in k or norm(k) == n: return v
    return None

# ═══════════════════ PLAYEROKAPI ═══════════════════
OK = False
Account = None
BotCheck = Unauth = Exception
try:
    from playerokapi.account import Account
    from playerokapi.exceptions import BotCheckDetectedException as BotCheck, UnauthorizedError as Unauth
    OK = True
    L.info("playerokapi OK")
except Exception as e: L.error("playerokapi: %s", e)

# ═══════════════════ STATE ═══════════════════
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
acc = None
stop = threading.Event()
state = {}
cache = {"chats": [], "ts": 0}
conn = {"ok": False, "err": "", "method": ""}
profile = {}
seen_m = set(SEEN_D.get("m") or [])
seen_d = set(SEEN_D.get("d") or []) | set(DEALS_D.keys())
last_bump = {"ts": 0}
plugin_apis = {}
ucache = {}
_update_check = {"ts": 0, "has": False, "remote": ""}

# ═══════════════════ HELPERS ═══════════════════
def esc(s): return str(s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def sv(v, d="—"):
    if v is None: return d
    s = str(v).strip()
    return s if s else d

def g(o, *attrs, default=None):
    for a in attrs:
        try:
            v = o.get(a) if isinstance(o, dict) else getattr(o, a, None)
            if v is not None and v != "": return v
        except Exception: continue
    return default

def is_authorized(uid):
    if uid == MAIN_ADMIN: return True
    return uid in USERS_STATE.get("authorized", [])

def adm(m):
    try: return is_authorized(int(m.chat.id))
    except Exception: return False

def send(cid, text, kb=None):
    try: bot.send_message(cid, text, reply_markup=kb, disable_web_page_preview=True)
    except Exception as e: L.debug("send: %s", e)

def notif(text, kb=None):
    if MAIN_ADMIN: send(MAIN_ADMIN, text, kb)

def edit(cid, mid, text, kb=None):
    try: bot.edit_message_text(text, cid, mid, reply_markup=kb)
    except Exception as e: L.debug("edit: %s", e)

def cookies(): return (CREDS.get("cookies") or "").strip()
def token_pk(): return (CREDS.get("token") or "").strip()
def ddg5(): return (CREDS.get("ddg5") or "").strip()

def cookie_str():
    p = []
    if token_pk(): p.append("token=" + token_pk())
    if ddg5(): p.append("__ddg5_=" + ddg5())
    for x in cookies().split(";"):
        x = x.strip()
        if x and x not in p: p.append(x)
    return ";".join(p)

# ═══════════════════ PLAYEROK API ═══════════════════
def get_chats():
    if acc is None: return []
    try:
        r = acc.get_chats()
        return list(getattr(r, "chats", None) or (r if isinstance(r, (list, tuple)) else []))
    except Exception: return []

def get_msgs(cid, n=24):
    if acc is None: return []
    try:
        r = acc.get_chat_messages(cid, count=n)
        return list(getattr(r, "messages", None) or (r if isinstance(r, (list, tuple)) else []))
    except Exception: return []

def get_deals():
    if acc is None: return []
    try:
        r = acc.get_deals()
        return list(getattr(r, "deals", None) or (r if isinstance(r, (list, tuple)) else []))
    except Exception: return []

def get_items():
    if acc is None: return []
    try:
        r = acc.get_my_items()
        return list(getattr(r, "items", None) or (r if isinstance(r, (list, tuple)) else []))
    except Exception: return []

def refresh_profile():
    global profile
    if acc is None: return
    try:
        profile = {"id": sv(g(acc, "id")), "username": sv(g(acc, "username")), "email": sv(g(acc, "email"))}
    except Exception: pass

# ═══════════════════ НИКИ ═══════════════════
UF = ("username","nickname","name","login","display_name")
UH = ("user","author","sender","from_user","from","companion","interlocutor","buyer","peer")

def deep_user(o, d=0, seen=None):
    if seen is None: seen = set()
    if o is None or d > 3: return ""
    if id(o) in seen: return ""
    seen.add(id(o))
    for f in UF:
        try:
            v = o.get(f) if isinstance(o, dict) else getattr(o, f, None)
            if isinstance(v, str) and 0 < len(v) < 80 and "@" not in v and "://" not in v: return v.strip()
        except Exception: continue
    for h in UH:
        try: s = o.get(h) if isinstance(o, dict) else getattr(o, h, None)
        except Exception: continue
        if s is None: continue
        if isinstance(s, str) and s.strip() and len(s) < 80: return s.strip()
        if isinstance(s, (dict, list, tuple)):
            for x in (s[:3] if isinstance(s, (list, tuple)) else [s]):
                r = deep_user(x, d+1, seen)
                if r: return r
        else:
            r = deep_user(s, d+1, seen)
            if r: return r
    return ""

def sender_name(chat, msg):
    cid = getattr(chat, "id", None) if chat else None
    n = chat_name(cid)
    if n: return n
    if msg:
        u = getattr(msg, "user", None)
        if u:
            for f in UF:
                v = getattr(u, f, None) if not isinstance(u, dict) else u.get(f)
                if v and isinstance(v, str) and v.strip(): return v.strip()
        for ha in ("author","sender","from_user"):
            h = getattr(msg, ha, None)
            if h is None: continue
            if isinstance(h, str) and h.strip(): return h.strip()
            for f in UF:
                v = getattr(h, f, None) if not isinstance(h, dict) else h.get(f)
                if v: return str(v)
    if chat:
        for ha in UH:
            h = getattr(chat, ha, None)
            if h is None: continue
            for f in UF:
                v = getattr(h, f, None) if not isinstance(h, dict) else h.get(f)
                if v: return str(v)
    r = deep_user(chat) or deep_user(msg)
    if r: return r
    if cid and str(cid) in ucache: return ucache[str(cid)]
    return "?"

def sender_id(chat, msg):
    for o in (msg, chat):
        if o is None: continue
        u = g(o, "user","author","sender","companion","interlocutor","buyer")
        if u:
            v = g(u, "id","user_id")
            if v: return str(v)
        v = g(o, "user_id","author_id","sender_id")
        if v: return str(v)
    return ""

def mtext(m):
    if m is None: return ""
    for f in ("text","content","body"):
        v = g(m, f)
        if v: return str(v)
    return ""

def mts(m):
    for f in ("created_at","timestamp","date","time"):
        v = g(m, f)
        if v: return str(v)
    return ""

def my_msg(m, chat=None):
    if m is None: return False
    myid = str(getattr(acc, "id", "") or "")
    myun = str(getattr(acc, "username", "") or "").lower()
    u = getattr(m, "user", None)
    if u:
        uid = getattr(u, "id", None) if not isinstance(u, dict) else u.get("id")
        if uid and myid and str(uid) == myid: return True
        un = getattr(u, "username", None) if not isinstance(u, dict) else u.get("username")
        if un and myun and str(un).lower() == myun: return True
    for f in ("is_my","own","from_me","outgoing"):
        v = getattr(m, f, None) if not isinstance(m, dict) else m.get(f)
        if v is True: return True
    return False

def mid(m):
    for f in ("id","message_id","uid"):
        v = g(m, f)
        if v: return str(v)
    t = mtext(m); ts = mts(m)
    if t or ts: return "h%d:%s" % (hash(t), ts)
    return ""

# ═══════════════════ AI ═══════════════════
AI_DEFAULTS = {
    "openai": ("https://api.openai.com/v1/chat/completions","gpt-4o-mini"),
    "anthropic": ("https://api.anthropic.com/v1/messages","claude-3-5-sonnet-latest"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/models/","gemini-2.0-flash"),
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions","openai/gpt-4o-mini"),
    "deepseek": ("https://api.deepseek.com/v1/chat/completions","deepseek-chat"),
    "groq": ("https://api.groq.com/openai/v1/chat/completions","meta-llama/llama-4-scout-17b-16e-instruct"),
}

AI_PROMPT = """Проверь изображение на нарушения правил маркетплейса Playerok.

ЗАПРЕЩЕНО (если есть — BAD):
1. Контакты: телефоны, email, @ники, Telegram, Телеграм, ТГ, WhatsApp, Ватсап, Viber, ВК, Discord, t.me, wa.me, vk.com, QR-коды, ссылки на сторонние сайты
2. Обход комиссии: напрямую, в лс, в личку, без комиссии, вне сайта, на карту, на СБП, сбер, тинькоф, USDT, BTC
3. Гарантии: гарантия, гарантирую, пожизненная, вечная, навсегда, 100% гарант, без гарантии, не несу ответственность, ответственность снимается. РАЗРЕШЕНО: "гарантия 48 часов" и больше, "гарантия до подтверждения"
4. Читы: чит, читы, cheat, hack, взлом, хакер
5. Запрещённые товары: VPN, proxy, tdata, token-акк, cookie-акк, рефанд, казино, ставки, 18+, эротика, 🔞, пиратство, торрент, кряк, смс-бомбер, DDoS, пробив, обнал, дропы, номера телефонов, госуслуги, паспорт, СНИЛС, курсы заработка
6. Оформление: имитация офиц. магазина Playerok, мат, оскорбления, политика, экстремизм
7. Недостоверность: случайная игра, рандом, от 1 до 10, прайс-лист, каталог, бартер, обмен

РАЗРЕШЕНО: игровые скриншоты, логотипы игр, стикеры/эмодзи, молния ⚡, 🔥, ⭐, 🎮, 💰, персонажи аниме/игр, инструкции, "гарантия 48 часов" и больше, "быстро", "premium", цены

ОТВЕТ: строго OK или BAD: <список>"""

def ai_call(body_builder, prov, key, model):
    from curl_cffi import requests as creq
    url, dmodel = AI_DEFAULTS.get(prov, AI_DEFAULTS["gemini"])
    model = model or dmodel
    H = {"Content-Type": "application/json"}
    if prov == "anthropic":
        H["x-api-key"] = key; H["anthropic-version"] = "2023-06-01"
        r = creq.post(url, json=body_builder(model, "anthropic"), headers=H, impersonate="chrome136", timeout=60)
        d = r.json()
        return (d.get("content", [{}])[0].get("text") or "").strip()
    if prov == "gemini":
        u = url + model + ":generateContent?key=" + key
        r = creq.post(u, json=body_builder(model, "gemini"), headers=H, impersonate="chrome136", timeout=60)
        d = r.json()
        try: return d["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception: return ""
    H["Authorization"] = "Bearer " + key
    if prov == "openrouter": H["HTTP-Referer"] = "https://playerok.com"
    r = creq.post(url, json=body_builder(model, "openai"), headers=H, impersonate="chrome136", timeout=60)
    d = r.json()
    return (d.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()

def ai_check_image(data, mime="image/jpeg"):
    if not AI_CONFIG.get("enabled"): return True, ""
    key = (AI_CONFIG.get("api_key") or "").strip()
    if not key: return True, ""
    import base64
    b64 = base64.b64encode(data).decode()
    prov = (AI_CONFIG.get("provider") or "gemini").lower()
    def _b(model, kind):
        if kind == "anthropic":
            return {"model": model, "max_tokens": 300, "messages": [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}},
                {"type": "text", "text": AI_PROMPT}]}]}
        if kind == "gemini":
            return {"contents": [{"parts": [{"text": AI_PROMPT},
                {"inline_data": {"mime_type": mime, "data": b64}}]}]}
        return {"model": model, "max_tokens": 300, "messages": [{"role": "user", "content": [
            {"type": "text", "text": AI_PROMPT},
            {"type": "image_url", "image_url": {"url": "data:" + mime + ";base64," + b64}}]}]}
    try:
        txt = ai_call(_b, prov, key, AI_CONFIG.get("model"))
        if not txt: return True, ""
        up = txt.upper()
        if up.startswith("OK"): return True, ""
        if up.startswith("BAD"): return False, (txt.split(":", 1)[1].strip() if ":" in txt else txt)
        return True, ""
    except Exception as e:
        L.warning("AI img: %s", str(e)[:150]); return True, ""

def ai_check_text(text):
    if not AI_CONFIG.get("enabled") or not text: return True, ""
    key = (AI_CONFIG.get("api_key") or "").strip()
    if not key: return True, ""
    prov = (AI_CONFIG.get("provider") or "gemini").lower()
    p = ("Проверь текст на нарушения правил Playerok. ЗАПРЕЩЕНО: контакты, обход комиссии, "
         "гарантии (кроме 48 часов и больше), читы, VPN, tdata, крипта, казино, 18+, пиратство, "
         "мат, имитация офиц. магазина, бартер, прайс-лист. Ответь OK или BAD: список. ТЕКСТ: " + text[:3000])
    def _b(model, kind):
        if kind == "anthropic": return {"model": model, "max_tokens": 200, "messages": [{"role": "user", "content": p}]}
        if kind == "gemini": return {"contents": [{"parts": [{"text": p}]}]}
        return {"model": model, "max_tokens": 200, "messages": [{"role": "user", "content": p}]}
    try:
        txt = ai_call(_b, prov, key, AI_CONFIG.get("model"))
        if not txt: return True, ""
        up = txt.upper()
        if up.startswith("OK"): return True, ""
        if up.startswith("BAD"): return False, (txt.split(":", 1)[1].strip() if ":" in txt else txt)
        return True, ""
    except Exception as e:
        L.warning("AI txt: %s", str(e)[:150]); return True, ""

def guard_photo(data, mime="image/jpeg", label="фото"):
    if not AI_CONFIG.get("enabled"): return True, ""
    ok, reason = ai_check_image(data, mime)
    if ok: return True, ""
    if AI_CONFIG.get("strict", True):
        return False, ("⚠️ <b>На " + label + " нарушения</b>\n\n<b>" + esc(reason[:400]) + "</b>\n\nЗамени фото.")
    notif("⚠️ <b>" + label + ":</b> " + esc(reason[:300]))
    return True, ""

# ═══════════════════ ЗАЩИТА ТЕКСТА ═══════════════════
import re as _reg

BANNED_PATTERNS = [
    (r"\+?\d[\d\s\-()]{9,}", "телефон"),
    (r"\b[\w.+-]+@[\w-]+\.[\w.-]+", "email"),
    (r"@[A-Za-z][A-Za-z0-9_]{3,}", "@ник"),
    (r"\b(telegram|телеграм|тг|tg|whatsapp|ватсап|viber|вайбер|discord|дискорд)\b", "мессенджер"),
    (r"\b(t\.me|wa\.me|vk\.com|insta(gram)?)\b", "соцсеть"),
    (r"\b(сбер|тинькоф|втб|сбп|qiwi|юмани|paypal|usdt|btc|bitcoin|крипта)\b", "платёжка/крипта"),
    (r"\b(напрямую|в\s+лс|в\s+личк[уе]|без\s+комисси|вне\s+сайта)\b", "обход комиссии"),
    (r"\b(переводом\s+на\s+карт|на\s+карту|оплата\s+напрямую)\b", "оплата вне сайта"),
    (r"\bгарант\w*\b", "гарантия"),
    (r"\b(пожизненн|вечн|навсегда|бессрочн)\w*\s+гарант", "пожизненная гарантия"),
    (r"100\s*%\s*гарант", "100% гарантия"),
    (r"\b(не\s+несу\s+ответствен|снимаю\s+с\s+себя|ответственность\s+снимается|не\s+отвечаю\s+за)\b", "снятие ответственности"),
    (r"\b(чит|читы|читов|читом|читер|cheat|hacks?|взлом|хакер)\w*", "читы/взлом"),
    (r"\b(vpn|впн|proxy|прокси|обход\s+блокировок)\b", "VPN/proxy"),
    (r"\b(tdata|тдата|token-акк|cookie-акк|рефанд)\b", "запрещ. товар"),
    (r"\b(казино|рулетк|букмекер|ставк|casino)\b", "казино/ставки"),
    (r"\b(18\+|🔞|эротик|порнограф|hentai|хентай|нюд|nude|nsfw)\w*", "18+"),
    (r"\b(пиратск|торрент|torrent|кряк|crack|репак|repack)\b", "пиратство"),
    (r"\b(кинопоиск|netflix|нетфликс|ivi|okko|кинотеатр)\b", "кинотеатр"),
    (r"\b(смс-бомбер|ddos|ддос|пробив|доксинг|обнал|дропы?)\b", "вредоносное"),
    (r"\b(номера?\s+телефон|аренда\s+номер|госуслуг|паспорт|снилс)\b", "перс.данные"),
    (r"\b(онлайн-курс|заработок\s+\d|финансов\w*\s+пирамид)\w*", "курсы/заработок"),
    (r"\b(политич|экстремизм|терроризм|нацизм|свастик)\w*", "политика"),
    (r"\b(бартер|свапа?ю|на\s+обмен|обмен\s+на)\b", "бартер"),
    (r"\b(прайс-лист|список\s+товаров|каталог\s+цен)\b", "прайс-лист"),
    (r"\b(оскорб|бля|хуй|пизд|fuck|shit)\w*", "мат"),
]

def validate_text(text):
    if not text: return True, []
    t = str(text).lower(); hits = []
    for pat, name in BANNED_PATTERNS:
        try:
            if _reg.search(pat, t, _reg.IGNORECASE | _reg.UNICODE): hits.append(name)
        except Exception: continue
    if "гарантия" in hits:
        allowed = _reg.search(r"гарант\w*\s+(?:на\s+)?(\d{2,}|48|72|90|180|365)\s*(?:час|ч|дн|дней|мес|год)", t)
        if allowed and not _reg.search(r"пожизн|навсегда|вечн|бессрочн|100%", t):
            hits = [h for h in hits if h != "гарантия"]
    return len(hits) == 0, hits

def guard_text(text, label="текст"):
    ok, hits = validate_text(text)
    if ok: return True, ""
    uniq = list(dict.fromkeys(hits))
    return False, ("⚠️ <b>Заблокировано правилами</b>\n\nВ " + label + ": <b>" + ", ".join(uniq) + "</b>\n\nПравила: playerok.com/terms-of-sale")

# ═══════════════════ LEGAL ═══════════════════
LEGAL_FOOTER = ("\n\n━━━━━━━━━━━━━━━━━━\nУсловия продажи: playerok.com/terms-of-sale\n"
                "Пользовательское соглашение: playerok.com/agreement\n"
                "Политика конфиденциальности: playerok.com/privacy\n"
                "Контакты: playerok.com/contacts\n━━━━━━━━━━━━━━━━━━")

def legal_wrap(d):
    d = (d or "").rstrip()
    if "terms-of-sale" in d: return d
    return d + LEGAL_FOOTER

# ═══════════════════ ПОДКЛЮЧЕНИЕ ═══════════════════
def connect():
    global acc
    if not OK: raise RuntimeError("playerokapi не установлен")
    ck = cookie_str()
    if not ck: raise RuntimeError("Нет cookies/token/ddg5")
    tries = []
    if token_pk() and ddg5(): tries.append(("token+ddg5", {"token": token_pk(), "ddg5": ddg5()}))
    tries.append(("cookies", {"cookies": ck}))
    if token_pk(): tries.append(("token", {"token": token_pk()}))
    errs = []
    for n, kw in tries:
        try:
            kw["user_agent"] = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/136.0.0.0"
            kw["requests_timeout"] = 30
            if PROXY: kw["proxy"] = PROXY
            L.info("connect %s", n)
            a = Account(**kw).get()
            if a is None: raise RuntimeError("None")
            acc = a
            conn.update({"ok": True, "err": "", "method": n})
            L.info("OK (%s) user=%s", n, getattr(a, "username", None))
            return a
        except BotCheck: errs.append(n + ": DDG")
        except Unauth: errs.append(n + ": 401")
        except Exception as e: errs.append(n + ": " + str(e)[:100])
    raise RuntimeError(" | ".join(errs))

# ═══════════════════ POLLER ═══════════════════
def poller():
    global cache
    L.info("poller started")
    back = 5
    while not stop.is_set():
        if acc is None:
            try:
                connect(); back = 5
                notif("🟢 " + INSTANCE_NAME + " подключён (" + conn.get("method", "") + ")")
            except Exception as e:
                L.error("connect: %s", str(e)[:200])
                if stop.wait(back): return
                back = min(back * 2, 120)
                if acc is None:
                    if stop.wait(15): return
                    continue
        try:
            now = time.time()
            if now - cache.get("ts", 0) > 60:
                cache["chats"] = get_chats(); cache["ts"] = now
            for d in get_deals():
                did = str(g(d, "id", "deal_id") or "")
                if did and did not in seen_d:
                    seen_d.add(did); on_deal(d)
            for ch in (cache.get("chats") or [])[:20]:
                cid = g(ch, "id", "chat_id")
                if not cid: continue
                for m in get_msgs(cid)[-8:]:
                    i = mid(m)
                    if not i or i in seen_m: continue
                    seen_m.add(i)
                    if my_msg(m, ch): continue
                    nm = sender_name(ch, m); txt = mtext(m)
                    if not txt: continue
                    ucache[str(cid)] = nm
                    if SET_D.get("notify_messages", True):
                        kb = K(row_width=2).row(B("📜 15", callback_data="c:" + str(cid)), B("✍️ Ответ", callback_data="r:" + str(cid)))
                        notif("💬 <b>" + esc(nm) + "</b>\n" + esc(txt[:400]), kb)
            try: refresh_profile()
            except Exception: pass
            save_seen()
            conn["ok"] = True
        except Exception as e:
            conn["ok"] = False; conn["err"] = str(e)[:150]; L.exception("poll")
        if stop.wait(15): return

def on_deal(d):
    did = str(g(d, "id", "deal_id") or "")
    st = str(g(d, "status", "state") or "").upper()
    u = g(d, "user", "buyer")
    buyer = sv(g(u, "username")) if u else "—"
    price = float(g(d, "price", "amount") or 0)
    DEALS_D[did] = {"id": did, "status": st, "buyer": buyer, "price": price}
    save_deals()
    em = {"PAID":"💳","CONFIRMED":"✅","CANCELED":"❌"}.get(st, "🛒")
    if SET_D.get("notify_deals", True):
        notif(em + " <b>Сделка " + esc(did[:16]) + "</b>\n👤 " + esc(buyer) + " · " + str(round(price)) + "₽ · " + esc(st))

# ═══════════════════ ОБНОВЛЕНИЕ ═══════════════════
def do_update(cid):
    if not GITHUB_REPO:
        send(cid, "❌ GitHub репозиторий не настроен"); return
    try:
        url = "https://raw.githubusercontent.com/" + GITHUB_REPO + "/" + GITHUB_BRANCH + "/" + GITHUB_FILE
        L.info("update: %s", url)
        opener = urllib.request.build_opener()
        if PROXY:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with opener.open(req, timeout=30) as r: code = r.read().decode("utf-8")
        if len(code) < 1000:
            send(cid, "❌ Файл слишком маленький"); return
        src_path = os.path.join(BASE_DIR, "pb.py")
        if os.path.exists(src_path):
            import shutil; shutil.copy(src_path, src_path + ".bak")
        with open(src_path, "w", encoding="utf-8") as f: f.write(code)
        send(cid, "✅ Обновлено! Перезапускаю...")
        time.sleep(2)
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        L.exception("update"); send(cid, "❌ " + esc(str(e)[:200]))

def get_remote_version():
    if not GITHUB_REPO: return None, "нет репо"
    try:
        url = "https://raw.githubusercontent.com/" + GITHUB_REPO + "/" + GITHUB_BRANCH + "/" + GITHUB_FILE
        opener = urllib.request.build_opener()
        if PROXY:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with opener.open(req, timeout=15) as r: code = r.read().decode("utf-8")
        m = re.search(r'BOT_VERSION\s*=\s*["\']([^"\']+)["\']', code)
        if m: return m.group(1), ""
        return None, "не нашёл версию"
    except Exception as e: return None, str(e)[:100]

def check_updates(silent=True):
    remote, err = get_remote_version()
    _update_check["ts"] = time.time()
    if err: return False, None, err
    if not remote: return False, None, "нет данных"
    has = remote != BOT_VERSION
    _update_check["has"] = has; _update_check["remote"] = remote
    if has and not silent:
        notif("🔄 Доступно обновление: <b>" + esc(remote) + "</b>\nТекущая: " + esc(BOT_VERSION) + "\n\nОбновить: /update")
    return has, remote, ""

def auto_update_worker():
    L.info("auto_update worker started (каждые 6 часов)")
    # Первая проверка через 5 минут после старта
    if stop.wait(5 * 60): return
    while not stop.is_set():
        try:
            has, remote, err = check_updates(silent=True)
            if has and SET_D.get("auto_update", True):
                notif("🔧 Автообновление: " + BOT_VERSION + " → " + remote)
                time.sleep(2)
                do_update(MAIN_ADMIN)
        except Exception as e: L.warning("auto_update: %s", e)
        if stop.wait(6 * 3600): return

# ═══════════════════ СОЗДАНИЕ ЛОТА ═══════════════════
def clone_item(cid, iid):
    try: it = acc.get_item(iid)
    except Exception as e:
        send(cid, "❌ " + esc(str(e)[:200])); return
    try:
        cat = g(it, "category"); obt = g(it, "obtaining_type")
        new = acc.create_item(
            game_category_id=cat.id if cat else None,
            obtaining_type_id=obt.id if obt else None,
            name=(it.name or "")[:80] + " (копия)",
            price=int(it.price or 0),
            description=getattr(it, "description", "") or "",
            options=getattr(it, "options", None) or [],
            data_fields=getattr(it, "data_fields", None) or [],
            attachments=[],
        )
        nid = str(g(new, "id") or "")
        send(cid, "✅ Создан лот: <code>" + esc(nid) + "</code>")
        show_item(cid, nid)
    except Exception as e:
        send(cid, "❌ Ошибка: " + esc(str(e)[:300]))

# ═══════════════════ UI ═══════════════════
def main_kb():
    kb = K(row_width=2)
    kb.row(B("🔌 Подключение", callback_data="conn"), B("📨 Чаты", callback_data="chats"))
    kb.row(B("🔔 Уведомления", callback_data="notify"), B("📋 Сделки", callback_data="deals"))
    kb.row(B("⚡ Автоподнятие", callback_data="bump"), B("📦 Мои лоты", callback_data="items:0"))
    kb.row(B("👤 Профиль", callback_data="prof"), B("🤖 AI-проверка", callback_data="ai"))
    kb.row(B("⚙️ Настройки", callback_data="set"), B("🛠 Обновить", callback_data="update"))
    kb.row(B("➕ Создать лот", callback_data="create_item"), B("🔄 Обновить меню", callback_data="menu"))
    return kb

def main_text():
    if acc is not None:
        try: refresh_profile()
        except Exception: pass
    conn_e = "🟢" if conn.get("ok") else "🔴"
    head = "🤖 <b>Playerok Bot</b> · <b>" + esc(INSTANCE_NAME) + "</b> · v" + BOT_VERSION + " · " + conn_e
    if acc is None: return head + "\n👤 Не подключён"
    d = profile or {}
    return (head + "\n👤 <b>" + esc(d.get("username") or "—") + "</b>\n" +
            "🆔 <code>" + esc(d.get("id") or "—") + "</code>\n" +
            "🛒 Сделок: <b>" + str(len(DEALS_D)) + "</b> · 📨 Чатов: <b>" + str(len(cache.get("chats", []))) + "</b>")

# ═══════════════════ КОМАНДЫ ═══════════════════
@bot.message_handler(commands=["start","menu"])
def cmd_start(m):
    if not adm(m):
        bot.reply_to(m, "⛔ Нет доступа. Введи пароль."); return
    state.pop(m.chat.id, None)
    bot.send_message(m.chat.id, main_text(), reply_markup=main_kb())

@bot.message_handler(commands=["id"])
def cmd_id(m): bot.reply_to(m, "🆔 <code>" + str(m.chat.id) + "</code>")

@bot.message_handler(commands=["restart"])
def cmd_restart(m):
    if not adm(m): return
    bot.reply_to(m, "🔄 Перезапускаю...")
    def _r():
        time.sleep(2); os.execv(sys.executable, [sys.executable] + sys.argv)
    threading.Thread(target=_r, daemon=True).start()

@bot.message_handler(commands=["update"])
def cmd_update(m):
    if not adm(m): return
    bot.reply_to(m, "📥 Скачиваю новый код с GitHub...")
    threading.Thread(target=do_update, args=(m.chat.id,), daemon=True).start()

@bot.message_handler(commands=["log"])
def cmd_log(m):
    if not adm(m): return
    try:
        with open(LOG_FILE, encoding="utf-8") as f: lines = f.readlines()[-300:]
        p = os.path.join(INST_DIR, "log_tail.txt")
        with open(p, "w", encoding="utf-8") as f: f.writelines(lines)
        with open(p, "rb") as f: bot.send_document(m.chat.id, f)
    except Exception as e: bot.reply_to(m, "❌ " + esc(str(e)))

@bot.message_handler(commands=["cancel"])
def cmd_cancel(m):
    state.pop(m.chat.id, None); bot.reply_to(m, "❌ Отменено")

# ═══════════════════ CALLBACKS ═══════════════════
@bot.callback_query_handler(func=lambda c: True)
def cb(c):
    if not is_authorized(int(c.from_user.id)):
        try: bot.answer_callback_query(c.id, "⛔")
        except Exception: pass
        return
    try: bot.answer_callback_query(c.id)
    except Exception: pass
    a = c.data; cid = c.message.chat.id; mid_ = c.message.id
    L.info("CB: %r", a)

    if a in ("menu","status","refresh"):
        edit(cid, mid_, main_text(), main_kb())
    elif a == "conn":
        lines = ["🔌 <b>Подключение</b>", "",
                 "🍪 cookies: <b>" + str(len(cookies())) + "</b>",
                 "🎫 token: <b>" + str(len(token_pk())) + "</b>",
                 "🛡 ddg5: <b>" + str(len(ddg5())) + "</b>",
                 "🌐 прокси: " + ("✅ " + PROXY if PROXY else "❌ нет"), ""]
        lines.append("✅ " + esc(sv(g(acc, "username"))) if acc else "❌ Не подключён")
        kb = K(row_width=1)
        kb.add(B("🍪 Cookies", callback_data="in_cookies"))
        kb.add(B("🎫 Token", callback_data="in_token"))
        kb.add(B("🛡 ddg5", callback_data="in_ddg5"))
        kb.add(B("🔄 Реконнект", callback_data="reconn"))
        kb.add(B("◀️", callback_data="menu"))
        edit(cid, mid_, "\n".join(lines), kb)
    elif a == "in_cookies":
        state[cid] = {"action": "cookies"}; bot.send_message(cid, "🍪 Cookie строку:\n\n/cancel")
    elif a == "in_token":
        state[cid] = {"action": "token"}; bot.send_message(cid, "🎫 JWT:\n\n/cancel")
    elif a == "in_ddg5":
        state[cid] = {"action": "ddg5"}; bot.send_message(cid, "🛡 __ddg5_:\n\n/cancel")
    elif a == "reconn":
        def _r():
            global acc
            acc = None
            try:
                connect(); refresh_profile()
                notif("🟢 " + INSTANCE_NAME + " переподключён")
            except Exception as e: notif("❌ " + esc(str(e)[:200]))
        threading.Thread(target=_r, daemon=True).start()
    elif a == "chats" or a == "chats_load":
        show_chats(cid, True)
    elif a.startswith("c:"): show_history(cid, a[2:])
    elif a.startswith("r:"):
        state[cid] = {"action": "reply", "chat": a[2:]}; bot.send_message(cid, "✍️ Текст ответа:\n\n/cancel")
    elif a == "deals": show_deals(cid)
    elif a == "notify": show_notify(cid)
    elif a.startswith("tog:"):
        k = a[4:]
        if k in SET_D:
            SET_D[k] = not SET_D[k]; save_set()
        if k in ("notify_messages","notify_deals","auto_confirm"): show_notify(cid)
        elif k == "auto_bump": show_bump(cid)
        elif k == "auto_update": show_set(cid)
    elif a == "bump": show_bump(cid)
    elif a.startswith("cyc:"):
        k = a[4:]
        cyc = {"auto_bump_min": [60,120,240,480,720], "auto_bump_max": [10,50,100,500,1000], "auto_confirm_delay": [10,30,60,120,300]}
        if k in cyc:
            try: cur = int(SET_D.get(k, cyc[k][0]))
            except Exception: cur = cyc[k][0]
            nxt = cyc[k][(cyc[k].index(cur)+1)%len(cyc[k])] if cur in cyc[k] else cyc[k][0]
            SET_D[k] = nxt; save_set()
        show_bump(cid)
    elif a == "prof":
        if acc is None: send(cid, "❌"); return
        refresh_profile()
        d = profile or {}
        txt = ("👤 <b>Профиль</b>\n\n🆔 <code>" + esc(d.get("id","—")) + "</code>\n👤 <b>" + esc(d.get("username","—")) + "</b>")
        send(cid, txt, K().add(B("◀️", callback_data="menu")))
    elif a == "set":
        auto = "✅ вкл" if SET_D.get("auto_update", True) else "❌ выкл"
        upd = "—"
        if _update_check.get("ts"):
            if _update_check.get("has"): upd = "🔄 " + _update_check.get("remote", "") + " доступна"
            else: upd = "✅ актуально"
        lines = ["⚙️ <b>Настройки</b>", "",
                 "🆔 Инстанс: <b>" + esc(INSTANCE_NAME) + "</b>",
                 "📦 Версия: <b>" + esc(BOT_VERSION) + "</b>",
                 "🔄 Автообновление: <b>" + auto + "</b>",
                 "📊 Обновление: " + upd,
                 "📁 Папка: <code>" + esc(INST_DIR) + "</code>",
                 "🔗 GitHub: " + (GITHUB_REPO if GITHUB_REPO else "не настроен")]
        kb = K(row_width=1)
        kb.add(B("🔍 Проверить обновления", callback_data="check_upd"))
        kb.add(B("🔄 Автообновление " + auto, callback_data="tog:auto_update"))
        kb.add(B("🛠 Обновить сейчас", callback_data="update"))
        kb.add(B("🔄 Перезапустить", callback_data="restart"))
        kb.add(B("📄 Лог", callback_data="log"))
        kb.add(B("◀️", callback_data="menu"))
        edit(cid, mid_, "\n".join(lines), kb)
    elif a == "check_upd":
        send(cid, "🔍 Проверяю...")
        def _cu():
            has, remote, err = check_updates(silent=True)
            if err: send(cid, "❌ " + esc(err))
            elif has:
                kb = K(row_width=2)
                kb.row(B("🔧 Обновить сейчас", callback_data="update"), B("◀️", callback_data="set"))
                send(cid, "🔄 <b>Доступно обновление!</b>\n\nТекущая: <b>" + esc(BOT_VERSION) + "</b>\nНовая: <b>" + esc(remote) + "</b>", kb)
            else:
                send(cid, "✅ <b>Актуальная версия:</b> " + esc(BOT_VERSION))
        threading.Thread(target=_cu, daemon=True).start()
    elif a == "update":
        send(cid, "📥 Скачиваю...")
        threading.Thread(target=do_update, args=(cid,), daemon=True).start()
    elif a == "restart":
        send(cid, "🔄"); time.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)
    elif a == "log": cmd_log(c)
    elif a == "ai": show_ai(cid)
    elif a == "ai_tog":
        AI_CONFIG["enabled"] = not AI_CONFIG.get("enabled", False); save_ai(); show_ai(cid)
    elif a == "ai_prov": show_ai_prov(cid)
    elif a.startswith("ai_setp:"):
        AI_CONFIG["provider"] = a.split(":",1)[1]; save_ai(); show_ai(cid)
    elif a == "ai_key":
        state[cid] = {"action": "ai_key"}; bot.send_message(cid, "🔑 Ключ:\n\n/cancel")
    elif a == "ai_model":
        state[cid] = {"action": "ai_model"}; bot.send_message(cid, "📝 Модель:\n\n/cancel")
    elif a == "ai_mode":
        AI_CONFIG["strict"] = not AI_CONFIG.get("strict", True); save_ai(); show_ai(cid)
    elif a == "ai_clear":
        AI_CONFIG["api_key"] = ""; AI_CONFIG["enabled"] = False; save_ai(); show_ai(cid)
    elif a == "ai_test":
        state[cid] = {"action": "ai_test"}; bot.send_message(cid, "🧪 Отправь фото или текст:\n\n/cancel")
    elif a == "ai_ping":
        send(cid, "🔗 Тест связи...")
        threading.Thread(target=ai_ping_task, args=(cid,), daemon=True).start()
    elif a == "create_item":
        send(cid, "➕ <b>Создание лота</b>\n\n"
                  "Открой любой лот из 📦 Мои лоты → нажми <b>📋 Копировать</b> — будет создан новый лот на основе старого.\n\n"
                  "Потом отредактируй его цену/название/описание/фото.")
    elif a.startswith("clone:"):
        iid = a[6:]
        send(cid, "⏳ Создаю копию...")
        threading.Thread(target=clone_item, args=(cid, iid), daemon=True).start()
    elif a == "items" or a.startswith("items:"):
        try: off = int(a.split(":")[1]) if ":" in a else 0
        except Exception: off = 0
        show_items(cid, off)
    elif a.startswith("it:"): show_item(cid, a[3:])
    elif a.startswith("edprice:"):
        state[cid] = {"action": "edprice", "id": a[8:]}; bot.send_message(cid, "💰 Цена:\n\n/cancel")
    elif a.startswith("edname:"):
        state[cid] = {"action": "edname", "id": a[7:]}; bot.send_message(cid, "📝 Название:\n\n/cancel")
    elif a.startswith("eddesc:"):
        state[cid] = {"action": "eddesc", "id": a[7:]}; bot.send_message(cid, "📄 Описание:\n\n/cancel")
    elif a.startswith("edphoto:"):
        state[cid] = {"action": "edphoto", "id": a[8:]}; bot.send_message(cid, "📷 Отправь фото:\n\n/cancel")
    elif a.startswith("disc1:"):
        state[cid] = {"action": "disc1", "id": a[6:]}; bot.send_message(cid, "💸 Скидка %:\n\n/cancel")
    elif a == "disc":
        state[cid] = {"action": "disc"}; bot.send_message(cid, "💰 Скидка % на все:\n\n/cancel")
    else: L.warning("CB unhandled: %r", a)

# ═══════════════════ SHOW ═══════════════════
def show_chats(cid, refresh=False):
    global cache
    if acc is None: send(cid, "❌"); return
    if refresh or time.time() - cache.get("ts", 0) > 30:
        cache["chats"] = get_chats(); cache["ts"] = time.time()
    chats = (cache.get("chats") or [])[:20]
    kb = K(row_width=1); lines = ["💬 <b>Чаты</b>", ""]
    if not chats: lines.append("<i>пусто</i>")
    for ch in chats:
        c = str(g(ch, "id", "chat_id") or "")
        n = chat_name(c) or sender_name(ch, None) or ucache.get(c, "?")
        lines.append("• <b>" + esc(n) + "</b>")
        kb.add(B("💬 " + n[:24], callback_data="c:" + c))
    kb.row(B("📥 Обновить", callback_data="chats_load"), B("◀️", callback_data="menu"))
    send(cid, "\n".join(lines), kb)

def show_history(cid, chat_id):
    if acc is None: send(cid, "❌"); return
    msgs = get_msgs(chat_id)[-15:]
    known = chat_name(chat_id)
    lines = ["💬 <b>" + esc(known or "чат") + "</b>", ""]
    for m in msgs:
        if my_msg(m): who = "🟦 Я"
        elif known: who = known
        else: who = "👤 " + sender_name(None, m)
        lines.append("<b>" + esc(who) + "</b> <i>" + esc(mts(m)) + "</i>")
        lines.append(esc(mtext(m)[:400])); lines.append("")
    kb = K(row_width=2)
    kb.row(B("📜 Обновить", callback_data="c:" + chat_id), B("✍️ Ответ", callback_data="r:" + chat_id))
    kb.add(B("◀️", callback_data="chats"))
    send(cid, "\n".join(lines), kb)

def show_deals(cid):
    deals = list(DEALS_D.values())[-20:]
    if not deals:
        send(cid, "📋 <b>Сделок нет</b>", K().add(B("◀️", callback_data="menu"))); return
    lines = ["📋 <b>Сделки</b>", ""]
    for d in deals:
        em = {"PAID":"💳","CONFIRMED":"✅","CANCELED":"❌"}.get(d.get("status",""), "•")
        lines.append(em + " <code>" + esc(d.get("id","")[:16]) + "</code> · " + esc(d.get("buyer","—")) + " · " + str(d.get("price",0)) + "₽")
    send(cid, "\n".join(lines), K(row_width=1).add(B("◀️", callback_data="menu")))

def show_notify(cid):
    kb = K(row_width=1)
    kb.add(B(("✅" if SET_D.get("notify_messages") else "⏸") + " Сообщения", callback_data="tog:notify_messages"))
    kb.add(B(("✅" if SET_D.get("notify_deals") else "⏸") + " Сделки", callback_data="tog:notify_deals"))
    kb.add(B(("✅" if SET_D.get("auto_confirm") else "⏸") + " Автоподтверждение", callback_data="tog:auto_confirm"))
    kb.add(B("◀️", callback_data="menu"))
    send(cid, "🔔 <b>Уведомления</b>", kb)

def show_bump(cid):
    on = SET_D.get("auto_bump")
    kb = K(row_width=2)
    kb.row(B("🔴 Выкл" if on else "🟢 Вкл", callback_data="tog:auto_bump"),
           B("⏱ " + str(SET_D.get("auto_bump_min",240)) + "м", callback_data="cyc:auto_bump_min"))
    kb.row(B("💰 " + str(SET_D.get("auto_bump_max",100)) + "₽", callback_data="cyc:auto_bump_max"),
           B("◀️", callback_data="menu"))
    send(cid, "⚡ <b>Автоподнятие</b>\nСтатус: <b>" + ("🟢 вкл" if on else "🔴 выкл") + "</b>", kb)

def show_items(cid, off=0):
    if acc is None: send(cid, "❌"); return
    items = get_items()
    kb = K(row_width=1); lines = ["📦 <b>Мои лоты</b>", ""]
    if not items: lines.append("<i>нет лотов</i>")
    for it in items[off:off+5]:
        iid = str(g(it, "id", "item_id") or "")
        name = sv(g(it, "name", "title"))
        try: price = int(g(it, "price", "amount") or 0)
        except Exception: price = 0
        lines.append("• <b>" + esc(name[:40]) + "</b> — " + str(price) + "₽")
        kb.add(B("📦 " + name[:20] + " · " + str(price) + "₽", callback_data="it:" + iid))
    kb.row(B("💰 Скидка на все", callback_data="disc"), B("◀️", callback_data="menu"))
    send(cid, "\n".join(lines), kb)

def _extract_attachment(it):
    """Вытаскивает attachment/attachments из лота. Возвращает FileObject или None."""
    v = g(it, "attachment")
    if v: return v
    v = g(it, "attachments")
    if isinstance(v, (list, tuple)) and v: return v[0]
    if v: return v
    return None

def show_item(cid, iid):
    if acc is None: send(cid, "❌"); return
    it = None
    try: it = acc.get_item(iid)
    except Exception:
        for x in get_items():
            if str(g(x, "id", "item_id")) == iid: it = x; break
    if not it: send(cid, "❌ Лот не найден"); return
    name = sv(g(it, "name", "title"))
    desc = sv(g(it, "description"), "нет описания")
    try: price = int(g(it, "price", "amount") or 0)
    except Exception: price = 0
    st = g(it, "status", "state")
    st_s = str(getattr(st, "name", st) or "—")
    lines = ["📦 <b>" + esc(name) + "</b>", "",
             "💰 Цена: <b>" + str(price) + "₽</b>",
             "📊 Статус: " + esc(st_s),
             "", "📝 " + esc(desc[:400])]
    kb = K(row_width=2)
    kb.row(B("💰 Цена", callback_data="edprice:" + iid), B("📝 Название", callback_data="edname:" + iid))
    kb.row(B("📄 Описание", callback_data="eddesc:" + iid), B("💸 Скидка", callback_data="disc1:" + iid))
    kb.row(B("📷 Сменить фото", callback_data="edphoto:" + iid), B("📋 Копировать", callback_data="clone:" + iid))
    kb.add(B("◀️", callback_data="items:0"))
    # Отправляем с фото если оно есть
    att = _extract_attachment(it)
    txt = "\n".join(lines)
    if att:
        try:
            bot.send_photo(cid, att, caption=txt[:1024], reply_markup=kb, parse_mode="HTML")
            return
        except Exception as e:
            L.debug("send_photo: %s", e)
    send(cid, txt, kb)

def show_ai(cid):
    c = AI_CONFIG
    on = c.get("enabled"); has_key = bool((c.get("api_key") or "").strip())
    lines = ["🤖 <b>AI-проверка</b>", "",
             "Статус: <b>" + ("🟢 вкл" if on else "🔴 выкл") + "</b>",
             "Режим: <b>" + ("🔒 блокировать" if c.get("strict") else "🟡 предупреждать") + "</b>",
             "Провайдер: <code>" + esc(c.get("provider") or "—") + "</code>",
             "Модель: <code>" + esc(c.get("model") or "(по умолчанию)") + "</code>",
             "Ключ: " + ("✅" if has_key else "❌")]
    kb = K(row_width=2)
    kb.row(B("🔴 Выкл" if on else "🟢 Вкл", callback_data="ai_tog"), B("🔒 Строго" if not c.get("strict") else "🟡 Мягко", callback_data="ai_mode"))
    kb.row(B("🔑 Ключ", callback_data="ai_key"), B("🎯 Провайдер", callback_data="ai_prov"))
    kb.row(B("📝 Модель", callback_data="ai_model"), B("🔗 Тест связи", callback_data="ai_ping"))
    kb.row(B("🧪 Тест фото/текст", callback_data="ai_test"), B("🗑 Сброс", callback_data="ai_clear"))
    kb.add(B("◀️", callback_data="menu"))
    send(cid, "\n".join(lines), kb)

def show_ai_prov(cid):
    kb = K(row_width=1)
    for p in AI_DEFAULTS.keys():
        cur = "✅ " if AI_CONFIG.get("provider") == p else ""
        kb.add(B(cur + p, callback_data="ai_setp:" + p))
    kb.add(B("◀️", callback_data="ai"))
    send(cid, "🎯 <b>Провайдер AI</b>\n\n"
              "<b>gemini</b> — AIzaSy... с aistudio.google.com (бесплатно)\n"
              "<b>openai</b> — sk-... с platform.openai.com\n"
              "<b>anthropic</b> — sk-ant-... с console.anthropic.com\n"
              "<b>openrouter</b> — sk-or-... с openrouter.ai\n"
              "<b>deepseek</b> — с platform.deepseek.com\n"
              "<b>groq</b> — с console.groq.com (бесплатно)", kb)

def ai_ping_task(cid):
    if not AI_CONFIG.get("enabled"): send(cid, "❌ AI выключен"); return
    key = (AI_CONFIG.get("api_key") or "").strip()
    if not key: send(cid, "❌ Нет ключа"); return
    prov = (AI_CONFIG.get("provider") or "gemini").lower()
    model = (AI_CONFIG.get("model") or "").strip() or AI_DEFAULTS[prov][1]
    t0 = time.time()
    try:
        def _b(model, kind):
            if kind == "anthropic": return {"model": model, "max_tokens": 20, "messages": [{"role": "user", "content": "Ответь: РАБОТАЕТ"}]}
            if kind == "gemini": return {"contents": [{"parts": [{"text": "Ответь: РАБОТАЕТ"}]}]}
            return {"model": model, "max_tokens": 20, "messages": [{"role": "user", "content": "Ответь: РАБОТАЕТ"}]}
        txt = ai_call(_b, prov, key, AI_CONFIG.get("model"))
        dt = time.time() - t0
        if txt:
            send(cid, "✅ <b>AI отвечает!</b>\n\nПровайдер: <code>" + esc(prov) + "</code>\nМодель: <code>" + esc(model) + "</code>\nОтвет: <i>" + esc(txt[:100]) + "</i>\nВремя: " + str(round(dt,1)) + " сек")
        else: send(cid, "❌ Пустой ответ")
    except Exception as e:
        send(cid, "❌ " + esc(str(e)[:250]))

# ═══════════════════ TEXT ═══════════════════
@bot.message_handler(content_types=["text"])
def handle_text(m):
    uid = int(m.chat.id) if m.chat.id else 0
    if not is_authorized(uid):
        if uid == MAIN_ADMIN:
            pass
        elif (m.text or "").strip() == ADMIN_PASSWORD and ADMIN_PASSWORD:
            if uid not in USERS_STATE.get("authorized", []):
                USERS_STATE.setdefault("authorized", []).append(uid); save_users()
            bot.reply_to(m, "✅ Добро пожаловать! Отправь /start"); return
        else:
            bot.reply_to(m, "🔐 Введи пароль для доступа:"); return

    st = state.get(m.chat.id)
    a = st.get("action") if isinstance(st, dict) else st
    if not a: return

    if a == "cookies":
        state.pop(m.chat.id, None); CREDS["cookies"] = (m.text or "").strip(); save_creds(); bot.reply_to(m, "✅ cookies")
    elif a == "token":
        state.pop(m.chat.id, None); CREDS["token"] = (m.text or "").strip(); save_creds(); bot.reply_to(m, "✅ token")
    elif a == "ddg5":
        state.pop(m.chat.id, None); CREDS["ddg5"] = (m.text or "").strip(); save_creds(); bot.reply_to(m, "✅ ddg5")
    elif a == "ai_key":
        state.pop(m.chat.id, None); AI_CONFIG["api_key"] = (m.text or "").strip(); AI_CONFIG["enabled"] = True; save_ai(); bot.reply_to(m, "✅ Ключ сохранён, AI включён")
    elif a == "ai_model":
        state.pop(m.chat.id, None); AI_CONFIG["model"] = (m.text or "").strip(); save_ai(); bot.reply_to(m, "✅ Модель")
    elif a == "ai_test":
        state.pop(m.chat.id, None); v = (m.text or "").strip()
        if not v: return
        bot.reply_to(m, "🔍 Проверяю...")
        def _t():
            ok, r = ai_check_text(v)
            if ok: bot.send_message(m.chat.id, "✅ Нарушений нет")
            else: bot.send_message(m.chat.id, "⚠️ <b>Найдено:</b>\n" + esc(r[:500]))
        threading.Thread(target=_t, daemon=True).start()
    elif a == "reply":
        state.pop(m.chat.id, None); cid = st.get("chat"); text = (m.text or "").strip()
        if not text: return
        okv, msg = guard_text(text, "сообщении")
        if not okv: bot.reply_to(m, msg); return
        try:
            acc.send_message(chat_id=cid, text=text); bot.reply_to(m, "✅ Отправлено")
        except Exception as e: bot.reply_to(m, "❌ " + esc(str(e)[:200]))
    elif a == "edprice":
        state.pop(m.chat.id, None); iid = st.get("id")
        try: p = int(float((m.text or "").strip().replace(",", ".")))
        except Exception: bot.reply_to(m, "❌ Число"); return
        try:
            it = acc.get_item(iid)
            acc.update_item(iid, name=it.name, price=p, description=getattr(it,"description","") or "", options=getattr(it,"options",None) or [], data_fields=getattr(it,"data_fields",None) or [])
            bot.reply_to(m, "✅ Цена " + str(p) + "₽"); show_item(m.chat.id, iid)
        except Exception as e: bot.reply_to(m, "❌ " + esc(str(e)[:200]))
    elif a == "edname":
        state.pop(m.chat.id, None); iid = st.get("id"); v = (m.text or "").strip()
        okv, msg = guard_text(v, "названии")
        if not okv: bot.reply_to(m, msg); return
        try:
            it = acc.get_item(iid)
            acc.update_item(iid, name=v, price=int(it.price), description=getattr(it,"description","") or "", options=getattr(it,"options",None) or [], data_fields=getattr(it,"data_fields",None) or [])
            bot.reply_to(m, "✅"); show_item(m.chat.id, iid)
        except Exception as e: bot.reply_to(m, "❌ " + esc(str(e)[:200]))
    elif a == "eddesc":
        state.pop(m.chat.id, None); iid = st.get("id"); v = (m.text or "").strip()
        okv, msg = guard_text(v, "описании")
        if not okv: bot.reply_to(m, msg); return
        try:
            it = acc.get_item(iid)
            acc.update_item(iid, name=it.name, price=int(it.price), description=legal_wrap(v), options=getattr(it,"options",None) or [], data_fields=getattr(it,"data_fields",None) or [])
            bot.reply_to(m, "✅"); show_item(m.chat.id, iid)
        except Exception as e: bot.reply_to(m, "❌ " + esc(str(e)[:200]))
    elif a == "disc":
        state.pop(m.chat.id, None)
        try: pct = float((m.text or "").strip().replace(",", "."))
        except Exception: bot.reply_to(m, "❌ Число"); return
        bot.reply_to(m, "⏳")
        def _d():
            ok = err = 0
            for it in get_items():
                try:
                    iid = g(it, "id", "item_id"); full = acc.get_item(iid)
                    new = int(round(float(full.price) * (1 - pct/100)))
                    acc.update_item(iid, name=full.name, price=new, description=getattr(full,"description","") or "", options=getattr(full,"options",None) or [], data_fields=getattr(full,"data_fields",None) or [])
                    ok += 1
                except Exception: err += 1
            bot.send_message(m.chat.id, "✅ " + str(ok) + ", ❌ " + str(err))
        threading.Thread(target=_d, daemon=True).start()
    elif a == "disc1":
        state.pop(m.chat.id, None); iid = st.get("id")
        try: pct = float((m.text or "").strip().replace(",", "."))
        except Exception: bot.reply_to(m, "❌"); return
        try:
            it = acc.get_item(iid); new = int(round(float(it.price) * (1 - pct/100)))
            acc.update_item(iid, name=it.name, price=new, description=getattr(it,"description","") or "", options=getattr(it,"options",None) or [], data_fields=getattr(it,"data_fields",None) or [])
            bot.reply_to(m, "✅ " + str(new) + "₽"); show_item(m.chat.id, iid)
        except Exception as e: bot.reply_to(m, "❌ " + esc(str(e)[:200]))

# ═══════════════════ PHOTO ═══════════════════
@bot.message_handler(content_types=["photo"])
def on_photo(m):
    if not adm(m): return
    st = state.get(m.chat.id)
    a = st.get("action") if isinstance(st, dict) else None
    if a == "edphoto":
        state.pop(m.chat.id, None); iid = st.get("id")
        try:
            f = bot.get_file(m.photo[-1].file_id); content = bot.download_file(f.file_path)
        except Exception as e: bot.reply_to(m, "❌ " + esc(str(e))); return
        okp, pmsg = guard_photo(content, "image/jpeg", "фото лота")
        if not okp: bot.reply_to(m, pmsg); return
        try:
            it = acc.get_item(iid)
            acc.update_item(iid, name=it.name, price=int(it.price), description=getattr(it,"description","") or "", options=getattr(it,"options",None) or [], data_fields=getattr(it,"data_fields",None) or [], add_attachments=[content])
            bot.reply_to(m, "✅ Фото обновлено"); show_item(m.chat.id, iid)
        except Exception as e: bot.reply_to(m, "❌ " + esc(str(e)[:250]))
    elif a == "ai_test":
        state.pop(m.chat.id, None)
        try:
            f = bot.get_file(m.photo[-1].file_id); content = bot.download_file(f.file_path)
        except Exception as e: bot.reply_to(m, "❌ " + esc(str(e))); return
        bot.reply_to(m, "🔍 Анализирую...")
        def _t():
            ok, r = ai_check_image(content, "image/jpeg")
            if ok: bot.send_message(m.chat.id, "✅ Нарушений нет")
            else: bot.send_message(m.chat.id, "⚠️ <b>Найдено:</b>\n" + esc(r[:500]))
        threading.Thread(target=_t, daemon=True).start()

# ═══════════════════ MAIN ═══════════════════
def main():
    L.info("=== Playerok Bot v" + BOT_VERSION + " — instance: " + INSTANCE_NAME + " ===")
    L.info("Папка инстанса: %s", INST_DIR)
    if OK and cookie_str():
        try:
            connect()
            threading.Thread(target=poller, name="poll", daemon=True).start()
            threading.Thread(target=auto_update_worker, name="upd", daemon=True).start()
            refresh_profile()
        except Exception as e: L.error("startup: %s", e)
    try:
        notif("🚀 <b>" + INSTANCE_NAME + "</b> v" + BOT_VERSION + " запущен\n🔗 GitHub: " + (GITHUB_REPO if GITHUB_REPO else "не настроен"))
    except Exception: pass
    L.info("telegram polling start")
    try:
        bot.infinity_polling(timeout=30, long_polling_timeout=30)
    except KeyboardInterrupt:
        stop.set(); save_seen()

if __name__ == "__main__":
    main()
