#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KiriillBR Playerok Bot v11.19 — фикс фото, автоответы, автоподтверждение для лотов."""
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

BOT_VERSION = "11.19"
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
    cfg["auto_update"] = False
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
if not _acquire_lock(): sys.exit(1)

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
    "auto_confirm_lots": [],
    "auto_confirm_reviews": False,
    "auto_confirm_review_text": "Спасибо за отзыв! Рад, что всё прошло хорошо 🙌",
    "auto_reply_purchase": True,
    "auto_reply_purchase_text": "Спасибо за покупку! Заказ #{deal_id} принят в работу. Если будут вопросы — пиши сюда 🙌",
    "auto_bump": False, "auto_bump_min": 240, "auto_bump_max": 100,
    "auto_update": False, "tmpl": "Здравствуйте, {buyer}! {message}",
})
for k in ("auto_confirm_lots","auto_confirm_reviews","auto_confirm_review_text","auto_reply_purchase","auto_reply_purchase_text"):
    if k not in SET_D:
        if k == "auto_confirm_lots": SET_D[k] = []
        elif k == "auto_confirm_reviews": SET_D[k] = False
        elif k == "auto_confirm_review_text": SET_D[k] = "Спасибо за отзыв! Рад, что всё прошло хорошо 🙌"
        elif k == "auto_reply_purchase": SET_D[k] = True
        elif k == "auto_reply_purchase_text": SET_D[k] = "Спасибо за покупку! Заказ #{deal_id} принят в работу. Если будут вопросы — пиши сюда 🙌"

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
# ФИКС: обработка статусов, шаблонов, ников
# ═══════════════════════════════════════════════════════════════
def status_name(raw):
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
    "ITEM_PAID":"💰 Оплачено", "ITEM_SENT":"📤 Отправлено", "ITEM_CONFIRMED":"✅ Подтверждено",
    "ITEM_CANCELED":"❌ Отменено", "ITEM_REFUNDED":"💸 Возврат", "ITEM_DEAL":"🛒 Сделка",
    "DEAL_PAID":"💰 Оплачено", "DEAL_SENT":"📤 Отправлено", "DEAL_CONFIRMED":"✅ Сделка подтверждена",
    "DEAL_CONFIRMED_AUTOMATICALLY":"✅ Автоподтверждение", "DEAL_CANCELED":"❌ Сделка отменена",
    "DEAL_CANCELLED":"❌ Сделка отменена", "DEAL_REFUNDED":"💸 Возврат по сделке",
    "DEAL_ROLLED_BACK":"↩️ Возврат средств", "DEAL_CREATED":"🆕 Сделка создана",
    "DEAL_HAS_PROBLEM":"⚠️ Проблема со сделкой", "DEAL_PROBLEM_RESOLVED":"✅ Проблема решена",
    "BUYER":"—","BUYER_NAME":"—","USERNAME":"—","SELLER":"—",
    "PRICE":"0","AMOUNT":"0","DEAL_ID":"","ID":"","STATUS":"",
}

def substitute_templates(text, buyer="", price=0, did="", status="", extra=None):
    if not text: return ""
    t = str(text).strip()
    local = dict(_TEMPLATE_MAP)
    local["BUYER"] = buyer or "—"; local["BUYER_NAME"] = buyer or "—"; local["USERNAME"] = buyer or "—"
    local["PRICE"] = str(round(price)) if price else "0"
    local["AMOUNT"] = str(round(price)) if price else "0"
    local["DEAL_ID"] = str(did or ""); local["ID"] = str(did or "")
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
            if isinstance(v, str) and v.strip() and v != "None": return v.strip()
        return ""
    for k in ("username","nickname","name","login","display_name"):
        try:
            v = getattr(obj, k, None)
            if isinstance(v, str) and v.strip() and v != "None": return v.strip()
        except Exception: continue
    return ""

def my_username():
    try: return str(getattr(acc, "username", "") or "").strip().lower()
    except Exception: return ""

def peer_in_chat(chat):
    users = None
    if isinstance(chat, dict): users = chat.get("users")
    else: users = getattr(chat, "users", None)
    if not users: return ""
    me = my_username()
    for u in users:
        un = username_of(u)
        if un and un.lower() != me: return un
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
# ФУНКЦИИ АВТО-ДЕЙСТВИЙ
# ═══════════════════════════════════════════════════════════════
def _auto_confirm_deal(deal_id):
    delay = int(SET_D.get("auto_confirm_delay", 30) or 30)
    L.info("auto_confirm: ждём %d сек для %s", delay, deal_id)
    time.sleep(delay)
    if acc is None: return
    try:
        if hasattr(acc, "confirm_deal"): acc.confirm_deal(deal_id)
        elif hasattr(acc, "confirm_order"): acc.confirm_order(deal_id)
        else:
            q = """mutation ConfirmDeal($dealId: ID!) { confirmDeal(dealId: $dealId) { id status } }"""
            if hasattr(acc, "make_request"): acc.make_request(q, {"dealId": str(deal_id)})
            else: raise RuntimeError("нет метода confirm")
        L.info("auto_confirm: ✅ %s", deal_id)
        d = DEALS_D.get(str(deal_id), {})
        notif(f"✅ <b>Автоподтверждение</b>\n🧾 {esc(str(deal_id)[:16])}\n👤 {esc(d.get('buyer','—'))}\n💵 {round(float(d.get('price',0) or 0))}₽")
    except Exception as e:
        L.error("auto_confirm: ❌ %s", e)
        notif(f"⚠️ <b>Автоподтверждение не удалось</b>\n#{esc(str(deal_id)[:16])}\n<i>{esc(str(e)[:200])}</i>")

def _auto_reply_to_review(deal_id, review_id, rating, buyer=""):
    if not SET_D.get("auto_confirm_reviews"): return
    text = str(SET_D.get("auto_confirm_review_text", "")).strip()
    if not text or not review_id or acc is None: return
    try:
        if hasattr(acc, "reply_to_review"): acc.reply_to_review(review_id, text)
        elif hasattr(acc, "answer_review"): acc.answer_review(review_id, text)
        else:
            q = """mutation ReplyReview($reviewId: ID!, $text: String!) { replyReview(reviewId: $reviewId, text: $text) { id } }"""
            if hasattr(acc, "make_request"): acc.make_request(q, {"reviewId": str(review_id), "text": text})
            else: raise RuntimeError("нет метода reply")
        L.info("auto_review: ✅ %s", review_id)
        notif(f"💬 <b>Автоответ на отзыв</b>\n🧾 #{esc(str(deal_id)[:16])}\n👤 {esc(buyer or '—')}\n{'⭐' * int(rating or 0)}\n\n<i>{esc(text[:200])}</i>")
    except Exception as e:
        L.error("auto_review: ❌ %s", e)
        notif(f"⚠️ Автоответ на отзыв не удался\n#{esc(str(deal_id)[:16])}\n<i>{esc(str(e)[:200])}</i>")

def _auto_reply_purchase(deal_id, buyer, price, item_name):
    if not SET_D.get("auto_reply_purchase"): return
    text = str(SET_D.get("auto_reply_purchase_text", "")).strip()
    if not text: return
    text = (text.replace("{deal_id}", str(deal_id)).replace("{buyer}", str(buyer or ""))
            .replace("{price}", str(round(price))).replace("{item}", str(item_name or "")))
    if acc is None: return
    try:
        chat_id = None
        try:
            deal = acc.get_deal(deal_id) if hasattr(acc, "get_deal") else None
            if deal: chat_id = g(deal, "chat_id", "chat")
        except Exception: pass
        if not chat_id:
            L.warning("auto_purchase: не нашёл chat_id для %s", deal_id)
            notif(f"⚠️ Автоответ на покупку: нет chat_id для #{esc(str(deal_id)[:16])}")
            return
        if hasattr(acc, "send_message"): acc.send_message(chat_id=chat_id, text=text)
        else:
            q = """mutation SendMessage($chatId: ID!, $text: String!) { sendMessage(chatId: $chatId, text: $text) { id } }"""
            if hasattr(acc, "make_request"): acc.make_request(q, {"chatId": str(chat_id), "text": text})
            else: raise RuntimeError("нет метода send_message")
        L.info("auto_purchase: ✅ отправлено %s", buyer)
        notif(f"✉️ <b>Автоответ на покупку</b>\n🧾 #{esc(str(deal_id)[:16])}\n👤 {esc(buyer or '—')}\n📦 {esc(str(item_name or '—')[:60])}")
    except Exception as e:
        L.error("auto_purchase: ❌ %s", e)
        notif(f"⚠️ Автоответ на покупку не удался\n#{esc(str(deal_id)[:16])}\n<i>{esc(str(e)[:200])}</i>")

def _should_auto_confirm(lot_name):
    if not SET_D.get("auto_confirm"): return False
    lots = SET_D.get("auto_confirm_lots") or []
    if not lots: return True
    ln = str(lot_name or "").lower()
    for pat in lots:
        try:
            if str(pat).lower() in ln: return True
        except Exception: continue
    return False

# ═══════════════════════════════════════════════════════════════
# УТИЛИТЫ
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

# ═══════════════════════════════════════════════════════════════
# ФИКС: ФОТО ЛОТОВ
# ═══════════════════════════════════════════════════════════════
def item_photos(it):
    out, seen = [], set()
    def _abs(u):
        if not u or not isinstance(u, str): return ""
        u = u.strip()
        if u.startswith("http"): return u
        if u.startswith("//"): return "https:" + u
        if u.startswith("/"): return "https://playerok.com" + u
        return ""
    def add(v):
        if not v: return
        if isinstance(v, str):
            u = _abs(v)
            if u and u not in seen: seen.add(u); out.append(u)
            return
        if isinstance(v, (list, tuple)):
            for x in v: add(x)
            return
        if isinstance(v, dict):
            for k in ("url","link","href","src","path","full","preview","file_url","image_url","download_url","original"):
                u = _abs(v.get(k))
                if u and u not in seen: seen.add(u); out.append(u)
            return
        for a in ("url","link","href","src","path","full","preview","file_url","image_url","download_url","original"):
            try:
                u = _abs(getattr(v, a, None))
                if u and u not in seen: seen.add(u); out.append(u)
            except Exception: continue
    for f in ("attachments","attachment","images","photos","files","banner","image","preview","thumbnail","picture","cover","main_image","photo","media","gallery","images_list","image_urls"):
        try:
            v = g(it, f)
            if v: add(v)
        except Exception: continue
    try:
        src = it if isinstance(it, dict) else vars(it)
        for k, v in src.items():
            kl = str(k).lower()
            if any(t in kl for t in ("attach","image","photo","banner","pic","cover","media","gallery")): add(v)
    except Exception: pass
    for attr in ("raw", "json", "json_data", "_raw"):
        try:
            rv = getattr(it, attr, None) or (it.get(attr) if isinstance(it, dict) else None)
            if rv: add(rv)
        except Exception: continue
    L.info("item_photos: %d фото для лота %s", len(out), g(it, "id", "item_id"))
    return out

def item_url(iid, it=None):
    if it:
        s = g(it, "slug")
        if s and isinstance(s, str) and s.strip():
            s = s.strip()
            if s.startswith("http"): return s
            if s.startswith("products/"): return "https://playerok.com/" + s
            return "https://playerok.com/products/" + s
    if iid: return "https://playerok.com/products/" + str(iid)
    return "https://playerok.com/"

# ═══════════════════════════════════════════════════════════════
# ФУНКЦИИ API
# ═══════════════════════════════════════════════════════════════
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
# AI (заглушка для совместимости)
# ═══════════════════════════════════════════════════════════════
AI_DEFAULTS = {"openai": ("https://api.openai.com/v1/chat/completions","gpt-4o-mini"), "gemini": ("https://generativelanguage.googleapis.com/v1beta/models/","gemini-2.0-flash")}
def ai_call(*a, **kw): raise RuntimeError("AI не настроен")
def ai_check_image(*a, **kw): return True, ""
def ai_check_text(*a, **kw): return True, ""
def guard_photo(*a, **kw): return True, ""
def guard_text_ai(*a, **kw): return True, ""
def guard_text(*a, **kw): return True, ""
def validate_text(t): return True, []
def legal_wrap(d): return d or ""

# ═══════════════════════════════════════════════════════════════
# ПОДКЛЮЧЕНИЕ
# ═══════════════════════════════════════════════════════════════
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
# POLLER
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
# ON_DEAL (с авто-действиями)
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
    if price == 0.0: price = old.get("price", 0.0)

    item_name = deal_item_name(d) or old.get("item", "")
    review_text = deal_review_text(d)
    review_rating = deal_review_rating(d)

    raw_msg = g(d, "message", "text", "description") or ""
    msg = substitute_templates(raw_msg, buyer=buyer, price=price, did=did, status=status_key)

    DEALS_D[did] = {
        "id": did, "status": status_key, "buyer": buyer,
        "price": price, "item": item_name, "message": msg,
        "review_text": review_text, "review_rating": review_rating,
    }
    save_deals()
    L.info("deal %s st=%s (old=%s) buyer=%s price=%s item=%s", did[:12], status_key, old_status, buyer, price, item_name[:40])

    if SET_D.get("notify_deals", True):
        em = status_emoji(status_key)
        if not first_time and old_status and old_status != status_key:
            header = f"🔄 <b>Сделка обновилась</b> · {esc(did[:16])}"
        else:
            header = f"{em} <b>Сделка {esc(did[:16])}</b>"
        lines = [header, f"👤 {esc(buyer)} · {round(price)}₽"]
        if item_name: lines.append(f"📦 {esc(item_name[:60])}")
        lines.append(f"📊 {esc(status_ru(status_key))}")
        if msg and msg != status_ru(status_key): lines += ["", f"💬 <i>{esc(msg[:400])}</i>"]
        if review_rating:
            lines += ["", f"🌟 <b>Отзыв {'⭐' * review_rating}</b>"]
            if review_text: lines.append(f"<i>{esc(review_text[:400])}</i>")
        notif("\n".join(lines))

    if status_key == "PAID" and first_time:
        if SET_D.get("auto_reply_purchase", True):
            threading.Thread(target=_auto_reply_purchase, args=(did, buyer, price, item_name), daemon=True).start()

    if status_key == "PAID" and SET_D.get("auto_confirm"):
        if _should_auto_confirm(item_name or msg or ""):
            threading.Thread(target=_auto_confirm_deal, args=(did,), daemon=True).start()

    if review_rating and SET_D.get("auto_confirm_reviews"):
        review_id = None
        try:
            _r = d.get("review") if isinstance(d, dict) else getattr(d, "review", None)
            if _r: review_id = _r.get("id") if isinstance(_r, dict) else getattr(_r, "id", None)
        except Exception: pass
        if review_id:
            threading.Thread(target=_auto_reply_to_review, args=(did, review_id, review_rating, buyer), daemon=True).start()

# ═══════════════════════════════════════════════════════════════
# UI
# ═══════════════════════════════════════════════════════════════
def main_kb():
    kb = K(row_width=2)
    kb.row(B("🔌 Подключение", callback_data="conn"), B("📨 Чаты", callback_data="chats"))
    kb.row(B("🔔 Уведомления", callback_data="notify"), B("📋 Сделки", callback_data="deals"))
    kb.row(B("📦 Мои лоты", callback_data="items:0"), B("👤 Профиль", callback_data="prof"))
    kb.row(B("⚙️ Настройки", callback_data="set"), B("🛠 Обновить", callback_data="update"))
    kb.row(B("🔄 Меню", callback_data="menu"))
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

def show_notify(cid):
    ac = "✅" if SET_D.get("auto_confirm") else "⏸"
    ar = "✅" if SET_D.get("auto_confirm_reviews") else "⏸"
    ap = "✅" if SET_D.get("auto_reply_purchase", True) else "⏸"
    lots = SET_D.get("auto_confirm_lots") or []
    lt = "все лоты" if not lots else f"{len(lots)} лот(ов)"
    kb = K(row_width=1)
    kb.add(B(("✅" if SET_D.get("notify_messages") else "⏸") + " Уведомления о сообщениях", callback_data="tog:notify_messages"))
    kb.add(B(("✅" if SET_D.get("notify_deals") else "⏸") + " Уведомления о сделках", callback_data="tog:notify_deals"))
    kb.add(B(f"{ap} Автоответ на покупку", callback_data="tog:auto_reply_purchase"))
    kb.add(B("✏️ Текст автоответа на покупку", callback_data="ac_purchase_text"))
    kb.add(B(f"{ac} Автоподтверждение", callback_data="tog:auto_confirm"))
    kb.add(B(f"⏱ Задержка: {SET_D.get('auto_confirm_delay', 30)} сек", callback_data="cyc:auto_confirm_delay"))
    kb.add(B(f"📦 Лоты: {lt}", callback_data="ac_lots_menu"))
    kb.add(B(f"{ar} Автоответ на отзывы", callback_data="tog:auto_confirm_reviews"))
    kb.add(B("✏️ Текст автоответа на отзыв", callback_data="ac_review_text"))
    kb.add(B("◀️", callback_data="menu"))
    txt = (f"🔔 <b>Уведомления и авто-действия</b>\n\n"
           f"Автоответ на покупку: <b>{'вкл' if SET_D.get('auto_reply_purchase', True) else 'выкл'}</b>\n"
           f"Автоподтверждение: <b>{'вкл' if SET_D.get('auto_confirm') else 'выкл'}</b>\n"
           f"Задержка: <b>{SET_D.get('auto_confirm_delay', 30)} сек</b>\n"
           f"Лоты: <b>{lt}</b>\n"
           f"Автоответ на отзывы: <b>{'вкл' if SET_D.get('auto_confirm_reviews') else 'выкл'}</b>")
    send(cid, txt, kb)

def show_ac_lots(cid):
    lots = SET_D.get("auto_confirm_lots") or []
    kb = K(row_width=1)
    if not lots:
        kb.add(B("📦 Все лоты (пусто = все)", callback_data="noop"))
    else:
        for i, lot in enumerate(lots):
            kb.add(B(f"🗑 {lot[:30]}", callback_data=f"ac_lot_del:{i}"))
    kb.add(B("➕ Добавить лот", callback_data="ac_lot_add"))
    kb.add(B("🗑 Очистить (все лоты)", callback_data="ac_lots_clear"))
    kb.add(B("◀️ Назад", callback_data="notify"))
    txt = (f"📦 <b>Лоты для автоподтверждения</b>\n\n"
           f"Пусто = подтверждать <b>все</b>.\n"
           f"Добавленные = фильтр по названию.\n\n"
           f"Сейчас: <b>{len(lots) if lots else 'все'}</b>")
    send(cid, txt, kb)

def show_items(cid, off=0):
    if acc is None: send(cid, "❌"); return
    items = get_items()
    kb = K(row_width=1); lines = ["📦 <b>Мои лоты</b>", ""]
    if not items: lines.append("<i>нет лотов</i>")
    
    confirm_lots = SET_D.get("auto_confirm_lots") or []
    
    for it in items[off:off+5]:
        iid = str(g(it, "id", "item_id") or "")
        name = sv(g(it, "name", "title"))
        try: price = int(g(it, "price", "amount") or 0)
        except Exception: price = 0
        photos = item_photos(it)
        mark = "🖼" if photos else "·"
        conf_mark = " ⚡" if name in confirm_lots else ""
        lines.append(mark + " <b>" + esc(name[:40]) + "</b> — " + str(price) + "₽" + conf_mark)
        kb.add(B("📦 " + name[:20] + " · " + str(price) + "₽" + conf_mark, callback_data="it:" + iid))
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
    photos = item_photos(it)
    
    confirm_lots = SET_D.get("auto_confirm_lots") or []
    if not SET_D.get("auto_confirm"):
        confirm_btn = "⚡ Автоподтверждение: ГЛОБАЛЬНО ВЫКЛ"
    elif not confirm_lots:
        confirm_btn = "✅ Автоподтверждение: ВСЕ ЛОТЫ"
    elif name in confirm_lots:
        confirm_btn = "✅ Автоподтверждение: ВКЛ"
    else:
        confirm_btn = "⏸ Автоподтверждение: ВЫКЛ"

    lines = ["📦 <b>" + esc(name) + "</b>", "", "💰 Цена: <b>" + str(price) + "₽</b>", "🖼 Фото: <b>" + str(len(photos)) + "</b>", "", "📝 " + esc(desc[:400])]
    kb = K(row_width=1)
    kb.add(B(confirm_btn, callback_data=f"tog_confirm_lot:{iid}"))
    kb.add(B("◀️ Назад", callback_data="items:0"))
    txt = "\n".join(lines)
    if photos:
        for u in photos[:3]:
            try:
                bot.send_photo(cid, u, caption=txt[:1024], reply_markup=kb, parse_mode="HTML"); return
            except Exception: pass
    send(cid, txt, kb)

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

# ═══════════════════════════════════════════════════════════════
# CALLBACKS
# ═══════════════════════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: True)
def on_cb(c):
    try: bot.answer_callback_query(c.id)
    except Exception: pass
    if not is_authorized(int(c.from_user.id)): return
    a = c.data; cid = c.message.chat.id; mid_ = c.message.id
    try:
        L.info("CB: %r", a)
        if a in ("menu","status","refresh"):
            _show_main_menu(cid, edit_mid=mid_)
        elif a == "notify":
            show_notify(cid)
        elif a == "ac_lots_menu":
            show_ac_lots(cid)
        elif a == "ac_lot_add":
            state[cid] = {"action": "ac_lot_add"}
            bot.send_message(cid, "📦 Отправь часть названия лота для автоподтверждения:\n\n/cancel — отмена")
        elif a.startswith("ac_lot_del:"):
            try: idx = int(a.split(":")[1])
            except Exception: idx = -1
            lots = SET_D.get("auto_confirm_lots") or []
            if 0 <= idx < len(lots):
                lots.pop(idx); SET_D["auto_confirm_lots"] = lots; save_set()
            show_ac_lots(cid)
        elif a == "ac_lots_clear":
            SET_D["auto_confirm_lots"] = []; save_set(); show_ac_lots(cid)
        elif a == "ac_review_text":
            state[cid] = {"action": "ac_review_text"}
            cur = SET_D.get("auto_confirm_review_text", "")
            bot.send_message(cid, f"✏️ Отправь новый текст автоответа на отзыв.\n\nСейчас: <i>{esc(cur[:200])}</i>\n\n/cancel — отмена")
        elif a == "ac_purchase_text":
            state[cid] = {"action": "ac_purchase_text"}
            cur = SET_D.get("auto_reply_purchase_text", "")
            bot.send_message(cid, f"✏️ Отправь новый текст автоответа на покупку.\n\nСейчас: <i>{esc(cur[:200])}</i>\n\n/cancel — отмена")
        elif a == "tog:notify_messages":
            SET_D["notify_messages"] = not SET_D.get("notify_messages"); save_set(); show_notify(cid)
        elif a == "tog:notify_deals":
            SET_D["notify_deals"] = not SET_D.get("notify_deals"); save_set(); show_notify(cid)
        elif a == "tog:auto_confirm":
            SET_D["auto_confirm"] = not SET_D.get("auto_confirm"); save_set(); show_notify(cid)
        elif a == "tog:auto_confirm_reviews":
            SET_D["auto_confirm_reviews"] = not SET_D.get("auto_confirm_reviews"); save_set(); show_notify(cid)
        elif a == "tog:auto_reply_purchase":
            SET_D["auto_reply_purchase"] = not SET_D.get("auto_reply_purchase", True); save_set(); show_notify(cid)
        elif a.startswith("cyc:auto_confirm_delay"):
            cur = int(SET_D.get("auto_confirm_delay", 30) or 30)
            nxt = {10:30, 30:60, 60:120, 120:300, 300:10}.get(cur, 30)
            SET_D["auto_confirm_delay"] = nxt; save_set(); show_notify(cid)
        elif a == "items" or a.startswith("items:"):
            try: off = int(a.split(":")[1]) if ":" in a else 0
            except Exception: off = 0
            show_items(cid, off)
        elif a.startswith("it:"): show_item(cid, a[3:])
        elif a.startswith("tog_confirm_lot:"):
            iid = a.split(":", 1)[1]
            it = None
            try: it = acc.get_item(iid) if acc else None
            except Exception: pass
            if not it:
                for x in get_items():
                    if str(g(x, "id", "item_id")) == iid: it = x; break
            if it:
                name = sv(g(it, "name", "title"))
                lots = SET_D.setdefault("auto_confirm_lots", [])
                if name in lots:
                    lots.remove(name)
                    try: bot.answer_callback_query(c.id, "Автоподтверждение для лота ВЫКЛ")
                    except Exception: pass
                else:
                    lots.append(name)
                    try: bot.answer_callback_query(c.id, "Автоподтверждение для лота ВКЛ")
                    except Exception: pass
                save_set()
            show_item(cid, iid)
        elif a == "deals": show_deals(cid)
        else: L.warning("CB unhandled: %r", a)
    except Exception as e:
        L.exception("cb error: %s", e)

# ═══════════════════════════════════════════════════════════════
# COMMANDS (ВАЖНО: ДО handle_text!)
# ═══════════════════════════════════════════════════════════════
@bot.message_handler(commands=["start","menu"])
def cmd_start(m):
    L.info("CMD /start from %s", m.chat.id)
    if not adm(m):
        L.warning("cmd_start: not authorized")
        bot.reply_to(m, "⛔ Нет доступа")
        return
    state.pop(m.chat.id, None)
    _show_main_menu(m.chat.id)

@bot.message_handler(commands=["id"])
def cmd_id(m):
    bot.reply_to(m, f"🆔 <code>{m.chat.id}</code>")

@bot.message_handler(commands=["cancel"])
def cmd_cancel(m):
    state.pop(m.chat.id, None)
    bot.reply_to(m, "❌ Отменено")

# ═══════════════════════════════════════════════════════════════
# TEXT
# ═══════════════════════════════════════════════════════════════
@bot.message_handler(content_types=["text"])
def handle_text(m):
    if (m.text or "").startswith("/"):
        return
    uid = int(m.chat.id) if m.chat.id else 0
    if not is_authorized(uid):
        bot.reply_to(m, "🔐 Введи пароль:"); return

    st = state.get(m.chat.id)
    a = st.get("action") if isinstance(st, dict) else st
    if not a: return

    if a == "ac_lot_add":
        state.pop(m.chat.id, None)
        t = (m.text or "").strip()
        if t:
            lots = SET_D.setdefault("auto_confirm_lots", [])
            if t not in lots:
                lots.append(t); save_set()
                bot.reply_to(m, f"✅ Добавлено в фильтр: <code>{esc(t)}</code>")
            else: bot.reply_to(m, "❌ Такой лот уже в списке")
        show_ac_lots(m.chat.id)
    elif a == "ac_review_text":
        state.pop(m.chat.id, None)
        t = (m.text or "").strip()
        if t:
            SET_D["auto_confirm_review_text"] = t; save_set()
            bot.reply_to(m, f"✅ Текст отзыва сохранён ({len(t)} симв.)")
        show_notify(m.chat.id)
    elif a == "ac_purchase_text":
        state.pop(m.chat.id, None)
        t = (m.text or "").strip()
        if t:
            SET_D["auto_reply_purchase_text"] = t; save_set()
            bot.reply_to(m, f"✅ Текст покупки сохранён ({len(t)} симв.)")
        show_notify(m.chat.id)

def main():
    L.info("=== Playerok Bot v" + BOT_VERSION + " · instance: " + INSTANCE_NAME + " ===")
    if OK and cookie_str():
        try:
            connect()
            threading.Thread(target=poller, name="poll", daemon=True).start()
            refresh_profile()
        except Exception as e: L.error("startup: %s", e)
    try: notif("🚀 <b>" + INSTANCE_NAME + "</b> v" + BOT_VERSION + " (pid " + str(os.getpid()) + ")")
    except Exception: pass
    try:
        bot.delete_webhook(drop_pending_updates=True)
        bot.set_my_commands([
            telebot.types.BotCommand("start", "🏠 Меню"),
            telebot.types.BotCommand("menu", "🔄 Меню"),
        ])
    except Exception as e: L.warning("setMyCommands: %s", e)
    L.info("telegram polling start")
    try: bot.infinity_polling(timeout=30, long_polling_timeout=30)
    except KeyboardInterrupt:
        stop.set(); save_seen()

if __name__ == "__main__":
    main()
