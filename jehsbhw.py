#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KiriillBR Playerok Bot v11.13 — фикс статусов/enum, UserProfile, шаблонов, отзывов, цены, отслеживание смены статуса."""
import os, sys, tempfile

os.environ.setdefault("SSL_CERT_FILE", "/etc/ssl/certs/ca-certificates.crt")
os.environ.setdefault("REQUESTS_CA_BUNDLE", "/etc/ssl/certs/ca-certificates.crt")
os.environ.setdefault("CURL_CA_BUNDLE", "/etc/ssl/certs/ca-certificates.crt")
_BOT_TMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp")
try:
    os.makedirs(_BOT_TMP, exist_ok=True)
    os.environ["TMPDIR"] = _BOT_TMP
    tempfile.tempdir = _BOT_TMP
except Exception: pass

import json, logging, re, threading, time, urllib.request, base64, fcntl, atexit
from datetime import datetime
from logging.handlers import RotatingFileHandler
import telebot
from telebot.types import InlineKeyboardMarkup as K, InlineKeyboardButton as B

BOT_VERSION = "11.13"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

def jload(p, d):
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except Exception: return d

def jsave(p, d):
    try:
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2, default=str)
            f.flush()
            try: os.fsync(f.fileno())
            except Exception: pass
        os.replace(tmp, p)
    except Exception as e: print("save", p, e)

def setup_logging():
    root = logging.getLogger(); root.setLevel(logging.DEBUG)
    for h in list(root.handlers): root.removeHandler(h)
    fmt = logging.Formatter("%(asctime)s,%(msecs)03d [%(levelname)-5s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    ch = logging.StreamHandler(sys.stdout); ch.setLevel(logging.INFO); ch.setFormatter(fmt); root.addHandler(ch)
    for n in ("urllib3","requests","curl_cffi","telebot","playerokapi","charset_normalizer"):
        logging.getLogger(n).setLevel(logging.WARNING)

setup_logging()
L = logging.getLogger("Bot")

def load_cfg(): return jload(CONFIG_FILE, {})
def save_cfg(c): jsave(CONFIG_FILE, c)

def setup_wizard():
    print("=" * 60); print("  Первый запуск KiriillBR Playerok Bot"); print("=" * 60); print()
    while True:
        nick = input("Ник бота: ").strip()
        nick = re.sub(r"[^A-Za-z0-9_\-]", "_", nick)[:32]
        if nick: break
    cfg = {"instance": nick}
    cfg["token"] = input("1. Токен бота: ").strip()
    cfg["admin_password"] = input("2. Пароль: ").strip()
    try: cfg["admin_id"] = int(input("3. Telegram ID: ").strip())
    except ValueError: cfg["admin_id"] = 0
    cfg["proxy"] = input("4. Прокси [Enter=нет]: ").strip()
    cfg["github_repo"] = input("5. GitHub owner/repo [Enter=silnikovkirill04-web/hehshe]: ").strip() or "silnikovkirill04-web/hehshe"
    cfg["github_branch"] = "main"
    cfg["github_file"] = "jehsbhw.py"
    cfg["auto_update"] = True
    save_cfg(cfg)
    print("\n✅ Сохранено:", CONFIG_FILE, "\n")
    return cfg

CFG = load_cfg()
if not CFG.get("token") or not CFG.get("admin_password") or not CFG.get("instance"):
    CFG = setup_wizard()

TOKEN = CFG["token"]
ADMIN_PASSWORD = CFG.get("admin_password", "")
MAIN_ADMIN = int(CFG.get("admin_id") or 0)
PROXY = CFG.get("proxy", "")
GITHUB_REPO = CFG.get("github_repo", "")
GITHUB_BRANCH = CFG.get("github_branch", "main")
GITHUB_FILE = CFG.get("github_file", "jehsbhw.py")
INSTANCE_NAME = CFG.get("instance", "default")

INST_DIR = os.path.join(BASE_DIR, INSTANCE_NAME)
os.makedirs(INST_DIR, exist_ok=True)

CREDS_FILE    = os.path.join(INST_DIR, "creds.json")
SETTINGS_FILE = os.path.join(INST_DIR, "settings.json")
DEALS_FILE    = os.path.join(INST_DIR, "deals.json")
USERS_FILE    = os.path.join(INST_DIR, "users.json")
AI_FILE       = os.path.join(INST_DIR, "ai_config.json")
NAMES_FILE    = os.path.join(INST_DIR, "chatnames.json")
PLUGINS_FILE  = os.path.join(INST_DIR, "plugins.json")
PLUGINS_DIR   = os.path.join(INST_DIR, "plugins")
SEEN_FILE     = os.path.join(INST_DIR, "seen.json")
DRAFT_FILE    = os.path.join(INST_DIR, "draft.json")
LOG_FILE      = os.path.join(INST_DIR, "bot.log")
LOCK_FILE     = os.path.join(INST_DIR, "bot.lock")
os.makedirs(PLUGINS_DIR, exist_ok=True)

_lock_fh = None
def _acquire_lock():
    global _lock_fh
    try:
        _lock_fh = open(LOCK_FILE, "w")
        fcntl.flock(_lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_fh.write(str(os.getpid())); _lock_fh.flush()
        atexit.register(lambda: (_lock_fh and _lock_fh.close()))
        return True
    except BlockingIOError:
        print("❌ Другой экземпляр уже запущен."); return False
    except Exception as e:
        print("lock warn:", e); return True
if not _acquire_lock():
    sys.exit(1)

try:
    fh = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=5, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s,%(msecs)03d [%(levelname)-5s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"))
    logging.getLogger().addHandler(fh)
except Exception as e: print("log file:", e)

if PROXY:
    try: telebot.apihelper.proxy = {"http": PROXY, "https": PROXY}
    except Exception: pass

CREDS = jload(CREDS_FILE, {"cookies": "", "token": "", "ddg5": ""})
SET_D = jload(SETTINGS_FILE, {
    "notify_messages": True, "notify_deals": True,
    "auto_confirm": False, "auto_confirm_delay": 30,
    "auto_bump": False, "auto_bump_min": 240, "auto_bump_max": 100,
    "auto_update": True, "tmpl": "Здравствуйте, {buyer}! {message}",
})
for _k in ("notify_messages","notify_deals","auto_confirm","auto_confirm_delay",
           "auto_bump","auto_bump_min","auto_bump_max","auto_update","tmpl"):
    if _k in CFG and _k not in SET_D:
        SET_D[_k] = CFG[_k]

DEALS_D = jload(DEALS_FILE, {})
USERS_STATE = jload(USERS_FILE, {"authorized": []})
if MAIN_ADMIN and MAIN_ADMIN not in USERS_STATE.get("authorized", []):
    USERS_STATE.setdefault("authorized", []).append(MAIN_ADMIN)
    jsave(USERS_FILE, USERS_STATE)
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

def save_seen():
    try:
        m = list(seen_m)[-5000:]; d = list(seen_d)[-5000:]
        jsave(SEEN_FILE, {"msgs": m, "deals": d})
    except Exception as e: L.warning("save_seen: %s", e)

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

OK = False; Account = None; BotCheck = Unauth = Exception
try:
    from playerokapi.account import Account
    from playerokapi.exceptions import BotCheckDetectedException as BotCheck, UnauthorizedError as Unauth
    OK = True; L.info("playerokapi OK")
except Exception as e: L.error("playerokapi: %s", e)

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
acc = None
stop = threading.Event()
state = {}
cache = {"chats": [], "ts": 0}
conn = {"ok": False, "err": "", "method": ""}
profile = {}
seen_m = set(SEEN_D.get("msgs") or [])
seen_d = set(SEEN_D.get("deals") or []) | set(DEALS_D.keys())
ucache = {}
_update_check = {"ts": 0, "has": False, "remote": ""}
DRAFT = jload(DRAFT_FILE, {})
LAST_MENU_MSG = {}

def save_draft(): jsave(DRAFT_FILE, DRAFT)

# ═══════════════════════════════════════════════════════════════
# ФИКС: enum, UserProfile, шаблоны, цена
# ═══════════════════════════════════════════════════════════════

def status_name(raw):
    """ItemDealStatuses.CONFIRMED -> CONFIRMED. Работает для enum и строк."""
    if raw is None: return ""
    name = getattr(raw, "name", None)
    if name: return str(name).upper()
    val = getattr(raw, "value", None)
    if val: return str(val).upper()
    s = str(raw)
    if "." in s: s = s.rsplit(".", 1)[-1]
    return s.strip().upper()

DEAL_STATUS_RU = {
    "PAID":"💰 Оплачено, ждём выдачу",
    "SENT":"📤 Товар отправлен",
    "CONFIRMED":"✅ Сделка подтверждена",
    "CONFIRMED_AUTOMATICALLY":"✅ Автоподтверждение",
    "PENDING":"⏳ Ожидание оплаты",
    "ROLLED_BACK":"↩️ Возврат средств",
}
DEAL_STATUS_EMOJI = {
    "PAID":"💳","SENT":"📤","CONFIRMED":"✅","CONFIRMED_AUTOMATICALLY":"✅",
    "PENDING":"⏳","ROLLED_BACK":"↩️",
}

def status_ru(raw):
    k = status_name(raw)
    return DEAL_STATUS_RU.get(k, k or "—")

def status_emoji(raw):
    k = status_name(raw)
    return DEAL_STATUS_EMOJI.get(k, "🛒")

_TEMPLATE_MAP = {
    "ITEM_PAID":"💰 Оплачено",
    "ITEM_SENT":"📤 Отправлено",
    "ITEM_CONFIRMED":"✅ Подтверждено",
    "ITEM_CANCELED":"❌ Отменено",
    "ITEM_REFUNDED":"💸 Возврат",
    "ITEM_DEAL":"🛒 Сделка",
    "DEAL_PAID":"💰 Оплачено",
    "DEAL_SENT":"📤 Отправлено",
    "DEAL_CONFIRMED":"✅ Сделка подтверждена",
    "DEAL_CONFIRMED_AUTOMATICALLY":"✅ Автоподтверждение",
    "DEAL_CANCELED":"❌ Сделка отменена",
    "DEAL_CANCELLED":"❌ Сделка отменена",
    "DEAL_REFUNDED":"💸 Возврат по сделке",
    "DEAL_ROLLED_BACK":"↩️ Возврат средств",
    "DEAL_CREATED":"🆕 Сделка создана",
    "DEAL_HAS_PROBLEM":"⚠️ Проблема со сделкой",
    "DEAL_PROBLEM_RESOLVED":"✅ Проблема решена",
    "BUYER":"—","BUYER_NAME":"—","USERNAME":"—","SELLER":"—",
    "PRICE":"0","AMOUNT":"0","DEAL_ID":"","ID":"","STATUS":"",
}

def substitute_templates(text, buyer="", price=0, did="", status="", extra=None):
    if not text: return ""
    t = str(text).strip()
    local = dict(_TEMPLATE_MAP)
    local["BUYER"] = buyer or "—"
    local["BUYER_NAME"] = buyer or "—"
    local["USERNAME"] = buyer or "—"
    local["PRICE"] = str(round(price)) if price else "0"
    local["AMOUNT"] = str(round(price)) if price else "0"
    local["DEAL_ID"] = str(did or "")
    local["ID"] = str(did or "")
    local["STATUS"] = status_ru(status)
    if extra: local.update(extra)

    def _r(m):
        k = (m.group(1) or "").strip().upper()
        if k in local: return str(local[k])
        k2 = k.rsplit(".", 1)[-1]
        return str(local.get(k2, ""))
    t = re.sub(r"\{\{\s*([A-Za-z0-9_.]+)\s*\}\}", _r, t)
    t = re.sub(r"\{\{[^}]{0,80}\}\}", "", t)
    return t.strip()

def username_of(obj):
    if obj is None: return ""
    if isinstance(obj, str):
        s = obj.strip()
        return s if s and s != "None" else ""
    if isinstance(obj, dict):
        for k in ("username","nickname","name","login","display_name"):
            v = obj.get(k)
            if isinstance(v, str) and v.strip() and v != "None":
                return v.strip()
        return ""
    for k in ("username","nickname","name","login","display_name"):
        try:
            v = getattr(obj, k, None)
            if isinstance(v, str) and v.strip() and v != "None":
                return v.strip()
        except Exception: continue
    return ""

def my_username():
    try:
        return str(getattr(acc, "username", "") or "").strip().lower()
    except Exception:
        return ""

def peer_in_chat(chat):
    users = None
    if isinstance(chat, dict): users = chat.get("users")
    else: users = getattr(chat, "users", None)
    if not users: return ""
    me = my_username()
    for u in users:
        un = username_of(u)
        if un and un.lower() != me:
            return un
    for u in users:
        un = username_of(u)
        if un: return un
    return ""

def peer_in_message(msg, chat=None):
    u = None
    if isinstance(msg, dict): u = msg.get("user")
    else: u = getattr(msg, "user", None)
    un = username_of(u)
    if un: return un
    if chat: return peer_in_chat(chat)
    return ""

def deal_price(d):
    """Пытается достать цену из многих полей."""
    if not d: return 0.0
    def _num(v):
        if v is None or v == "" or str(v) == "None": return None
        try: return float(v)
        except Exception: return None
    tr = d.get("transaction") if isinstance(d, dict) else getattr(d, "transaction", None)
    if tr and str(tr) != "None":
        for k in ("amount","price","value","total","sum","rub","price_rub"):
            n = _num(tr.get(k) if isinstance(tr, dict) else getattr(tr, k, None))
            if n is not None: return n
    for k in ("price","amount","total","sum","cost","price_rub","sum_rub"):
        n = _num(d.get(k) if isinstance(d, dict) else getattr(d, k, None))
        if n is not None: return n
    it = d.get("item") if isinstance(d, dict) else getattr(d, "item", None)
    if it and str(it) != "None":
        for k in ("price","amount","cost","total","price_rub","sum"):
            n = _num(it.get(k) if isinstance(it, dict) else getattr(it, k, None))
            if n is not None: return n
    pr = d.get("props") if isinstance(d, dict) else getattr(d, "props", None)
    if isinstance(pr, dict):
        for k in ("price","amount","total","sum"):
            n = _num(pr.get(k))
            if n is not None: return n
    logs = d.get("logs") if isinstance(d, dict) else getattr(d, "logs", None)
    if isinstance(logs, list):
        for lg in logs:
            if isinstance(lg, dict):
                for k in ("price","amount","total"):
                    n = _num(lg.get(k))
                    if n is not None: return n
    return 0.0

def deal_item_name(d):
    it = None
    if isinstance(d, dict): it = d.get("item")
    else: it = getattr(d, "item", None)
    if not it: return ""
    v = it.get("name") if isinstance(it, dict) else getattr(it, "name", None)
    return str(v).strip() if v and str(v) != "None" else ""

def deal_review_text(d):
    r = None
    if isinstance(d, dict): r = d.get("review")
    else: r = getattr(d, "review", None)
    if not r or str(r) == "None": return ""
    for k in ("text","comment","content"):
        v = r.get(k) if isinstance(r, dict) else getattr(r, k, None)
        if isinstance(v, str) and v.strip() and v != "None": return v.strip()
    return ""

def deal_review_rating(d):
    r = None
    if isinstance(d, dict): r = d.get("review")
    else: r = getattr(d, "review", None)
    if not r or str(r) == "None": return 0
    v = r.get("rating") if isinstance(r, dict) else getattr(r, "rating", None)
    try: return int(v) if v is not None else 0
    except Exception: return 0

# ═══════════════════════════════════════════════════════════════
# Утилиты
# ═══════════════════════════════════════════════════════════════
def esc(s): return str(s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def sv(v, d="—"):
    if v is None: return d
    s = str(v).strip()
    return s if s and s != "None" else d

def g(o, *attrs, default=None):
    for a in attrs:
        try:
            v = o.get(a) if isinstance(o, dict) else getattr(o, a, None)
            if v is not None and v != "" and str(v) != "None": return v
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
    try:
        bot.edit_message_text(text, cid, mid, reply_markup=kb, disable_web_page_preview=True)
        return True
    except Exception as e:
        emsg = str(e).lower()
        if "not modified" in emsg: return True
        try: bot.delete_message(cid, mid)
        except Exception: pass
        try:
            bot.send_message(cid, text, reply_markup=kb, disable_web_page_preview=True)
            return False
        except Exception as e2:
            L.debug("edit+send fail: %s / %s", e, e2)
            return False

def _show_main_menu(cid, edit_mid=None):
    state.pop(cid, None)
    old = LAST_MENU_MSG.pop(cid, None)
    if old and old != edit_mid:
        try: bot.delete_message(cid, old)
        except Exception: pass
    if edit_mid:
        if edit(cid, edit_mid, main_text(), main_kb()):
            LAST_MENU_MSG[cid] = edit_mid; return
    try:
        msg = bot.send_message(cid, main_text(), reply_markup=main_kb(),
                               disable_web_page_preview=True)
        LAST_MENU_MSG[cid] = msg.message_id
    except Exception as e:
        L.debug("_show_main_menu send: %s", e)

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

def mtext(m):
    if m is None: return ""
    for f in ("text","content","body"):
        v = g(m, f)
        if v and str(v) != "None": return str(v)
    return ""

def mts(m):
    for f in ("created_at","timestamp","date","time"):
        v = g(m, f)
        if v and str(v) != "None": return str(v)
    return ""

def my_msg(m, chat=None):
    if m is None: return False
    me = my_username()
    if not me: return False
    u = None
    if isinstance(m, dict): u = m.get("user")
    else: u = getattr(m, "user", None)
    un = username_of(u).lower()
    if un and un == me: return True
    for f in ("is_my","own","from_me","outgoing"):
        v = getattr(m, f, None) if not isinstance(m, dict) else m.get(f)
        if v is True: return True
    return False

def mid(m):
    for f in ("id","message_id","msg_id","uid"):
        v = g(m, f)
        if v and str(v) != "None": return str(v)
    t = mtext(m); ts = mts(m)
    if t or ts: return "h%d:%s" % (hash(t), ts)
    return ""

# ═══════════════════════════════════════════════════════════════
# AI
# ═══════════════════════════════════════════════════════════════
AI_DEFAULTS = {
    "openai": ("https://api.openai.com/v1/chat/completions","gpt-4o-mini"),
    "anthropic": ("https://api.anthropic.com/v1/messages","claude-3-5-sonnet-latest"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/models/","gemini-2.0-flash"),
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions","openai/gpt-4o-mini"),
    "deepseek": ("https://api.deepseek.com/v1/chat/completions","deepseek-chat"),
    "groq": ("https://api.groq.com/openai/v1/chat/completions","meta-llama/llama-4-scout-17b-16e-instruct"),
}
AI_PROMPT = "Проверь изображение на нарушения правил Playerok. ЗАПРЕЩЕНО: контакты, обход комиссии, гарантии, читы, VPN, казино, 18+, пиратство, DDoS, госуслуги, политика, мат. ОТВЕТ: строго OK или BAD: <список>"

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
    b64 = base64.b64encode(data).decode()
    prov = (AI_CONFIG.get("provider") or "gemini").lower()
    def _b(model, kind):
        if kind == "anthropic":
            return {"model": model, "max_tokens": 300, "messages": [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}},
                {"type": "text", "text": AI_PROMPT}]}]}
        if kind == "gemini":
            return {"contents": [{"parts": [{"text": AI_PROMPT}, {"inline_data": {"mime_type": mime, "data": b64}}]}]}
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
    p = "Проверь текст на нарушения правил Playerok. Ответь OK или BAD: список. ТЕКСТ: " + text[:3000]
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

BANNED_PATTERNS = [
    (r"\+?\d[\d\s\-()]{9,}", "телефон"),
    (r"\b[\w.+-]+@[\w-]+\.[\w.-]+", "email"),
    (r"@[A-Za-z][A-Za-z0-9_]{3,}", "@ник"),
    (r"\b(telegram|телеграм|тг|tg|whatsapp|ватсап|viber|вайбер|discord|дискорд)\b", "мессенджер"),
    (r"\b(t\.me|wa\.me|vk\.com|insta(gram)?)\b", "соцсеть"),
    (r"\b(сбер|тинькоф|втб|сбп|qiwi|юмани|paypal|usdt|btc|bitcoin|крипта)\b", "платёжка"),
    (r"\b(напрямую|в\s+лс|в\s+личк[уе]|без\s+комисси|вне\s+сайта)\b", "обход комиссии"),
    (r"\b(чит|читы|читов|читом|читер|cheat|hacks?|взлом|хакер)\w*", "читы"),
    (r"\b(vpn|впн|proxy|прокси)\b", "VPN"),
    (r"\b(казино|рулетк|букмекер|ставк|casino)\b", "казино"),
    (r"\b(18\+|🔞|эротик|порнограф|hentai|хентай|нюд|nude|nsfw)\w*", "18+"),
    (r"\b(пиратск|торрент|torrent|кряк|crack|репак|repack)\b", "пиратство"),
    (r"\b(оскорб|бля|хуй|пизд|fuck|shit)\w*", "мат"),
]

def validate_text(text):
    if not text: return True, []
    t = str(text).lower(); hits = []
    for pat, name in BANNED_PATTERNS:
        try:
            if re.search(pat, t, re.IGNORECASE | re.UNICODE): hits.append(name)
        except Exception: continue
    return len(hits) == 0, hits

def guard_text(text, label="текст"):
    ok, hits = validate_text(text)
    if ok: return True, ""
    uniq = list(dict.fromkeys(hits))
    return False, ("⚠️ <b>Заблокировано</b>\n\nВ " + label + ": <b>" + ", ".join(uniq) + "</b>")

LEGAL_FOOTER = ("\n\n━━━━━━━━━━━━━━━━━━\nУсловия продажи: playerok.com/terms-of-sale\n"
                "Пользовательское соглашение: playerok.com/agreement\n"
                "Политика конфиденциальности: playerok.com/privacy\n━━━━━━━━━━━━━━━━━━")

def legal_wrap(d):
    d = (d or "").rstrip()
    if "terms-of-sale" in d: return d
    return d + LEGAL_FOOTER

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

# ═══════════════════════════════════════════════════════════════
# POLLER — ловит новые + смену статуса
# ═══════════════════════════════════════════════════════════════
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
                if not did: continue
                new_status = status_name(g(d, "status", "state") or "")
                old = DEALS_D.get(did, {})
                old_status = old.get("status", "")
                if did not in seen_d:
                    seen_d.add(did)
                    on_deal(d, first_time=True)
                elif new_status and new_status != old_status:
                    L.info("deal %s changed %s -> %s", did[:12], old_status, new_status)
                    on_deal(d, first_time=False)

            new_msgs = 0
            for ch in (cache.get("chats") or [])[:20]:
                cid = g(ch, "id", "chat_id")
                if not cid: continue
                peer = peer_in_chat(ch)
                for m in get_msgs(cid)[-8:]:
                    i = mid(m)
                    if not i or i in seen_m: continue
                    seen_m.add(i); new_msgs += 1
                    if my_msg(m, ch): continue
                    nm = peer_in_message(m, ch) or peer or "—"
                    txt_raw = mtext(m)
                    if not txt_raw or txt_raw == "None": continue
                    txt = substitute_templates(txt_raw, buyer=nm)
                    ucache[str(cid)] = nm
                    if SET_D.get("notify_messages", True):
                        kb = K(row_width=2).row(
                            B("📜 15", callback_data="c:" + str(cid)),
                            B("✍️ Ответ", callback_data="r:" + str(cid)))
                        notif("💬 <b>" + esc(nm) + "</b>\n" + esc(txt[:400]), kb)
            if new_msgs: save_seen()
            try: refresh_profile()
            except Exception: pass
            conn["ok"] = True
        except Exception as e:
            conn["ok"] = False; conn["err"] = str(e)[:150]; L.exception("poll")
        if stop.wait(15): return

# ═══════════════════════════════════════════════════════════════
# ON_DEAL
# ═══════════════════════════════════════════════════════════════
def on_deal(d, first_time=True):
    did = str(g(d, "id", "deal_id") or "")
    raw_status = g(d, "status", "state") or ""
    status_key = status_name(raw_status)

    old = DEALS_D.get(did, {})
    old_status = old.get("status", "")

    u_obj = d.get("user") if isinstance(d, dict) else getattr(d, "user", None)
    buyer = username_of(u_obj)
    if not buyer:
        ch = d.get("chat") if isinstance(d, dict) else getattr(d, "chat", None)
        if ch: buyer = peer_in_chat(ch)
    if not buyer or buyer == "None": buyer = old.get("buyer") or "покупатель"

    price = deal_price(d)
    if price == 0.0:
        price = old.get("price", 0.0)

    item_name = deal_item_name(d) or old.get("item", "")
    review_text = deal_review_text(d)
    review_rating = deal_review_rating(d)

    raw_msg = g(d, "message", "text", "description") or ""
    msg = substitute_templates(raw_msg, buyer=buyer, price=price, did=did, status=status_key)

    DEALS_D[did] = {
        "id": did, "status": status_key, "buyer": buyer,
        "price": price, "item": item_name,
        "message": msg,
        "review_text": review_text, "review_rating": review_rating,
    }
    save_deals()
    L.info("deal %s st=%s (old=%s) buyer=%s price=%s item=%s",
           did[:12], status_key, old_status, buyer, price, item_name[:40])

    if not SET_D.get("notify_deals", True): return

    em = status_emoji(status_key)
    if not first_time and old_status and old_status != status_key:
        header = f"🔄 <b>Сделка обновилась</b> · {esc(did[:16])}"
    else:
        header = f"{em} <b>Сделка {esc(did[:16])}</b>"

    lines = [header, f"👤 {esc(buyer)} · {round(price)}₽"]
    if item_name: lines.append(f"📦 {esc(item_name[:60])}")
    lines.append(f"📊 {esc(status_ru(status_key))}")
    if msg and msg != status_ru(status_key):
        lines += ["", f"💬 <i>{esc(msg[:400])}</i>"]
    if review_rating:
        stars = "⭐" * review_rating
        lines += ["", f"🌟 <b>Отзыв {stars}</b>"]
        if review_text: lines.append(f"<i>{esc(review_text[:400])}</i>")
    notif("\n".join(lines))

# ═══════════════════════════════════════════════════════════════
# AUTO-UPDATE
# ═══════════════════════════════════════════════════════════════
def _fetch_remote():
    url = "https://raw.githubusercontent.com/" + GITHUB_REPO + "/" + GITHUB_BRANCH + "/" + GITHUB_FILE
    opener = urllib.request.build_opener()
    if PROXY:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with opener.open(req, timeout=30) as r:
        return r.read().decode("utf-8")

def do_update(cid):
    if not GITHUB_REPO: send(cid, "❌ GitHub не настроен"); return
    try:
        code = _fetch_remote()
        if len(code) < 1000: send(cid, "❌ Файл слишком маленький"); return
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
        code = _fetch_remote()
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
        notif("🔄 Доступно: " + esc(remote) + " (текущая " + esc(BOT_VERSION) + ")")
    return has, remote, ""

def auto_update_worker():
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

# ═══════════════════════════════════════════════════════════════
# UI
# ═══════════════════════════════════════════════════════════════
def main_kb():
    kb = K(row_width=2)
    kb.row(B("🔌 Подключение", callback_data="conn"), B("📨 Чаты", callback_data="chats"))
    kb.row(B("🔔 Уведомления", callback_data="notify"), B("📋 Сделки", callback_data="deals"))
    kb.row(B("📦 Мои лоты", callback_data="items:0"), B("👤 Профиль", callback_data="prof"))
    kb.row(B("🤖 AI-проверка", callback_data="ai"), B("⚙️ Настройки", callback_data="set"))
    kb.row(B("🛠 Обновить", callback_data="update"), B("🔄 Меню", callback_data="menu"))
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

@bot.message_handler(commands=["start","menu"])
def cmd_start(m):
    if not adm(m): bot.reply_to(m, "⛔ Нет доступа"); return
    state.pop(m.chat.id, None)
    DRAFT.pop(str(m.chat.id), None); save_draft()
    _show_main_menu(m.chat.id)

@bot.message_handler(commands=["id"])
def cmd_id(m): bot.reply_to(m, "🆔 <code>" + str(m.chat.id) + "</code>")

@bot.message_handler(commands=["restart"])
def cmd_restart(m):
    if not adm(m): return
    bot.reply_to(m, "🔄")
    def _r():
        time.sleep(2); os.execv(sys.executable, [sys.executable] + sys.argv)
    threading.Thread(target=_r, daemon=True).start()

@bot.message_handler(commands=["update"])
def cmd_update(m):
    if not adm(m): return
    bot.reply_to(m, "📥 Скачиваю...")
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
    state.pop(m.chat.id, None)
    DRAFT.pop(str(m.chat.id), None); save_draft()
    bot.reply_to(m, "❌ Отменено")

@bot.callback_query_handler(func=lambda c: True)
def cb(c):
    try: bot.answer_callback_query(c.id)
    except Exception: pass
    if not is_authorized(int(c.from_user.id)): return
    a = c.data; cid = c.message.chat.id; mid_ = c.message.id
    try:
        L.info("CB: %r", a)
        if a in ("menu","status","refresh"):
            _show_main_menu(cid, edit_mid=mid_)
        elif a == "conn":
            lines = ["🔌 <b>Подключение</b>", "",
                     "🍪 cookies: <b>" + str(len(cookies())) + "</b>",
                     "🎫 token: <b>" + str(len(token_pk())) + "</b>",
                     "🛡 ddg5: <b>" + str(len(ddg5())) + "</b>", ""]
            lines.append("✅ " + esc(sv(g(acc, "username"))) if acc else "❌ Не подключён")
            if conn.get("err"): lines.append("⚠️ <i>" + esc(conn["err"]) + "</i>")
            kb = K(row_width=1)
            kb.add(B("🔄 Реконнект", callback_data="reconn"))
            kb.add(B("◀️", callback_data="menu"))
            edit(cid, mid_, "\n".join(lines), kb)
        elif a == "reconn":
            send(cid, "🔄 Переподключаюсь...")
            def _r():
                global acc
                acc = None
                try:
                    connect(); refresh_profile()
                    send(cid, "🟢 Подключено: " + esc(sv(g(acc,"username"))))
                except Exception as e:
                    send(cid, "❌ " + esc(str(e)[:250]))
            threading.Thread(target=_r, daemon=True).start()
        elif a in ("chats","chats_load"): show_chats(cid, True)
        elif a.startswith("c:"): show_history(cid, a[2:])
        elif a.startswith("r:"):
            state[cid] = {"action": "reply", "chat": a[2:]}
            bot.send_message(cid, "✍️ Текст:\n\n/cancel")
        elif a == "deals": show_deals(cid)
        elif a == "notify": show_notify(cid)
        elif a.startswith("tog:"):
            k = a[4:]
            if k in SET_D: SET_D[k] = not SET_D[k]; save_set()
            if k in ("notify_messages","notify_deals","auto_confirm"): show_notify(cid)
        elif a == "prof":
            if acc is None: send(cid, "❌"); return
            refresh_profile(); d = profile or {}
            txt = ("👤 <b>Профиль</b>\n\n🆔 <code>" + esc(d.get("id","—")) + "</code>\n👤 <b>" + esc(d.get("username","—")) + "</b>")
            send(cid, txt, K().add(B("◀️", callback_data="menu")))
        elif a == "set":
            auto = "✅ вкл" if SET_D.get("auto_update", True) else "❌ выкл"
            upd = "—"
            if _update_check.get("ts"):
                upd = ("🔄 " + _update_check.get("remote","") + " доступна") if _update_check.get("has") else "✅ актуально"
            lines = ["⚙️ <b>Настройки</b>", "",
                     "🆔 Инстанс: <b>" + esc(INSTANCE_NAME) + "</b>",
                     "📦 Версия: <b>" + esc(BOT_VERSION) + "</b>",
                     "🔄 Автообновление: <b>" + auto + "</b>",
                     "📊 " + upd]
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
                    kb.row(B("🔧 Обновить", callback_data="update"), B("◀️", callback_data="set"))
                    send(cid, "🔄 Доступно: <b>" + esc(remote) + "</b>\nТекущая: <b>" + esc(BOT_VERSION) + "</b>", kb)
                else: send(cid, "✅ Актуальная: <b>" + esc(BOT_VERSION) + "</b>")
            threading.Thread(target=_cu, daemon=True).start()
        elif a == "update":
            send(cid, "📥 Скачиваю с GitHub...")
            threading.Thread(target=do_update, args=(cid,), daemon=True).start()
        elif a == "restart":
            send(cid, "🔄"); time.sleep(1); os.execv(sys.executable, [sys.executable] + sys.argv)
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
            state[cid] = {"action": "ai_test"}; bot.send_message(cid, "🧪 Фото или текст:\n\n/cancel")
        elif a == "ai_ping":
            send(cid, "🔗 Тест...")
            threading.Thread(target=ai_ping_task, args=(cid,), daemon=True).start()
        elif a == "items" or a.startswith("items:"):
            try: off = int(a.split(":")[1]) if ":" in a else 0
            except Exception: off = 0
            show_items(cid, off)
        elif a.startswith("it:"): show_item(cid, a[3:])
        else: L.warning("CB unhandled: %r", a)
    except Exception as e:
        L.exception("cb error: %s", e)
        try: bot.send_message(cid, "❌ Ошибка: " + esc(str(e)[:200]))
        except Exception: pass

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
        nm = chat_name(c) or peer_in_chat(ch) or "?"
        lines.append("• <b>" + esc(nm) + "</b>")
        kb.add(B("💬 " + nm[:24], callback_data="c:" + c))
    kb.row(B("📥 Обновить", callback_data="chats_load"), B("◀️", callback_data="menu"))
    send(cid, "\n".join(lines), kb)

def show_history(cid, chat_id):
    if acc is None: send(cid, "❌"); return
    msgs = get_msgs(chat_id)[-15:]
    ch = None
    for c in (cache.get("chats") or []):
        if str(g(c, "id", "chat_id") or "") == str(chat_id): ch = c; break
    peer = peer_in_chat(ch) if ch else ""
    known = chat_name(chat_id) or peer
    lines = ["💬 <b>" + esc(known or "чат") + "</b>", ""]
    for m in msgs:
        if my_msg(m): who = "🟦 Я"
        else: who = peer_in_message(m, ch) or known or "👤"
        txt = substitute_templates(mtext(m))
        if not txt or txt == "None": continue
        lines.append("<b>" + esc(who) + "</b> <i>" + esc(mts(m)) + "</i>")
        lines.append(esc(txt[:400])); lines.append("")
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
        st = d.get("status", "")
        em = status_emoji(st)
        it = d.get("item", "")
        line = em + " <code>" + esc(d.get("id","")[:16]) + "</code> · " + esc(d.get("buyer","—")) + " · " + str(round(d.get("price",0))) + "₽"
        if it: line += " · " + esc(it[:30])
        line += " · " + esc(status_ru(st))
        lines.append(line)
    send(cid, "\n".join(lines), K(row_width=1).add(B("◀️", callback_data="menu")))

def show_notify(cid):
    kb = K(row_width=1)
    kb.add(B(("✅" if SET_D.get("notify_messages") else "⏸") + " Сообщения", callback_data="tog:notify_messages"))
    kb.add(B(("✅" if SET_D.get("notify_deals") else "⏸") + " Сделки", callback_data="tog:notify_deals"))
    kb.add(B(("✅" if SET_D.get("auto_confirm") else "⏸") + " Автоподтверждение", callback_data="tog:auto_confirm"))
    kb.add(B("◀️", callback_data="menu"))
    send(cid, "🔔 <b>Уведомления</b>", kb)

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
    kb.add(B("◀️", callback_data="menu"))
    send(cid, "\n".join(lines), kb)

def show_item(cid, iid):
    if acc is None: send(cid, "❌"); return
    it = None
    try: it = acc.get_item(iid)
    except Exception:
        for x in get_items():
            if str(g(x, "id", "item_id")) == iid: it = x; break
    if not it: send(cid, "❌ Не найден"); return
    name = sv(g(it, "name", "title"))
    desc = sv(g(it, "description"), "нет описания")
    try: price = int(g(it, "price", "amount") or 0)
    except Exception: price = 0
    lines = ["📦 <b>" + esc(name) + "</b>", "",
             "💰 Цена: <b>" + str(price) + "₽</b>", "",
             "📝 " + esc(desc[:400])]
    kb = K(row_width=1).add(B("◀️", callback_data="items:0"))
    send(cid, "\n".join(lines), kb)

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
    kb.row(B("🔴 Выкл" if on else "🟢 Вкл", callback_data="ai_tog"),
           B("🔒 Строго" if not c.get("strict") else "🟡 Мягко", callback_data="ai_mode"))
    kb.row(B("🔑 Ключ", callback_data="ai_key"), B("🎯 Провайдер", callback_data="ai_prov"))
    kb.row(B("📝 Модель", callback_data="ai_model"), B("🔗 Тест связи", callback_data="ai_ping"))
    kb.row(B("🧪 Тест", callback_data="ai_test"), B("🗑 Сброс", callback_data="ai_clear"))
    kb.add(B("◀️", callback_data="menu"))
    send(cid, "\n".join(lines), kb)

def show_ai_prov(cid):
    kb = K(row_width=1)
    for p in AI_DEFAULTS.keys():
        cur = "✅ " if AI_CONFIG.get("provider") == p else ""
        kb.add(B(cur + p, callback_data="ai_setp:" + p))
    kb.add(B("◀️", callback_data="ai"))
    send(cid, "🎯 Провайдер", kb)

def ai_ping_task(cid):
    if not AI_CONFIG.get("enabled"): send(cid, "❌ выкл"); return
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
        if txt: send(cid, "✅ AI отвечает\n\n" + esc(prov) + " · " + esc(model) + "\n<i>" + esc(txt[:100]) + "</i>\n" + str(round(dt,1)) + "с")
        else: send(cid, "❌ Пустой")
    except Exception as e: send(cid, "❌ " + esc(str(e)[:250]))

@bot.message_handler(content_types=["text"])
def handle_text(m):
    uid = int(m.chat.id) if m.chat.id else 0
    if not is_authorized(uid):
        if (m.text or "").strip() == ADMIN_PASSWORD and ADMIN_PASSWORD:
            if uid not in USERS_STATE.get("authorized", []):
                USERS_STATE.setdefault("authorized", []).append(uid); save_users()
            bot.reply_to(m, "✅ Добро пожаловать! /start"); return
        bot.reply_to(m, "🔐 Введи пароль:"); return

    st = state.get(m.chat.id)
    a = st.get("action") if isinstance(st, dict) else st
    if not a: return

    if a == "ai_key":
        state.pop(m.chat.id, None)
        AI_CONFIG["api_key"] = (m.text or "").strip(); AI_CONFIG["enabled"] = True
        save_ai(); bot.reply_to(m, "✅ Ключ сохранён")
    elif a == "ai_model":
        state.pop(m.chat.id, None); AI_CONFIG["model"] = (m.text or "").strip(); save_ai(); bot.reply_to(m, "✅")
    elif a == "ai_test":
        state.pop(m.chat.id, None); v = (m.text or "").strip()
        if not v: return
        bot.reply_to(m, "🔍...")
        def _t():
            ok, r = ai_check_text(v)
            if ok: bot.send_message(m.chat.id, "✅ Нарушений нет")
            else: bot.send_message(m.chat.id, "⚠️ " + esc(r[:500]))
        threading.Thread(target=_t, daemon=True).start()
    elif a == "reply":
        state.pop(m.chat.id, None); cid_chat = st.get("chat"); text = (m.text or "").strip()
        if not text: return
        okv, msg = guard_text(text, "сообщении")
        if not okv: bot.reply_to(m, msg); return
        bot.reply_to(m, "🔍 Проверяю AI...")
        def _rc():
            ok_ai, reason = ai_check_text(text)
            if not ok_ai:
                bot.send_message(m.chat.id, "⚠️ <b>AI не пропустил:</b>\n\n" + esc(reason[:500])); return
            try:
                acc.send_message(chat_id=cid_chat, text=text)
                bot.send_message(m.chat.id, "✅ Отправлено")
            except Exception as e: bot.send_message(m.chat.id, "❌ " + esc(str(e)[:200]))
        threading.Thread(target=_rc, daemon=True).start()

@bot.message_handler(content_types=["photo"])
def on_photo(m):
    if not adm(m): return
    st = state.get(m.chat.id)
    a = st.get("action") if isinstance(st, dict) else None
    if a == "ai_test":
        state.pop(m.chat.id, None)
        try:
            f = bot.get_file(m.photo[-1].file_id); content = bot.download_file(f.file_path)
        except Exception as e: bot.reply_to(m, "❌ " + esc(str(e))); return
        bot.reply_to(m, "🔍...")
        def _t():
            ok, r = ai_check_image(content, "image/jpeg")
            if ok: bot.send_message(m.chat.id, "✅ Нарушений нет")
            else: bot.send_message(m.chat.id, "⚠️ " + esc(r[:500]))
        threading.Thread(target=_t, daemon=True).start()

def main():
    L.info("=== Playerok Bot v" + BOT_VERSION + " · instance: " + INSTANCE_NAME + " ===")
    L.info("Папка: %s", INST_DIR)
    if OK and cookie_str():
        try:
            connect()
            threading.Thread(target=poller, name="poll", daemon=True).start()
            threading.Thread(target=auto_update_worker, name="upd", daemon=True).start()
            refresh_profile()
        except Exception as e: L.error("startup: %s", e)
    try: notif("🚀 <b>" + INSTANCE_NAME + "</b> v" + BOT_VERSION + " (pid " + str(os.getpid()) + ")")
    except Exception: pass
    try:
        bot.delete_webhook(drop_pending_updates=True)
    except Exception as e: L.warning("delete_webhook: %s", e)
    try:
        bot.set_my_commands([
            telebot.types.BotCommand("start",  "🏠 Меню"),
            telebot.types.BotCommand("menu",   "🔄 Обновить меню"),
            telebot.types.BotCommand("id",     "🆔 Мой ID"),
            telebot.types.BotCommand("cancel", "❌ Отмена"),
            telebot.types.BotCommand("restart","🔄 Перезапуск"),
            telebot.types.BotCommand("update", "📥 Обновить"),
            telebot.types.BotCommand("log",    "📄 Лог"),
        ])
    except Exception as e: L.warning("setMyCommands: %s", e)
    L.info("telegram polling start")
    try: bot.infinity_polling(timeout=30, long_polling_timeout=30)
    except KeyboardInterrupt:
        stop.set(); save_seen()

if __name__ == "__main__":
    main()
