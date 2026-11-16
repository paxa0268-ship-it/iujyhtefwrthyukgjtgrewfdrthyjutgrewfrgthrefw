"""Sozlamalar: hammasi muhit o'zgaruvchilaridan (Render > Environment) olinadi."""
import hashlib
import os
import sys
from zoneinfo import ZoneInfo


def _e(name: str, default: str = "") -> str:
    v = os.getenv(name)
    return v.strip() if v and v.strip() else default


_missing = [n for n in ("BOT_TOKEN", "ANTHROPIC_API_KEY", "OWNER_ID") if not _e(n)]
if _missing:
    sys.stderr.write(
        "XATO: quyidagi muhit o'zgaruvchilari kiritilmagan: " + ", ".join(_missing) + "\n"
        "Render > Environment bo'limiga qo'shing (README.md ga qarang).\n"
    )
    sys.exit(1)

BOT_TOKEN = _e("BOT_TOKEN")
ANTHROPIC_API_KEY = _e("ANTHROPIC_API_KEY")
try:
    OWNER_ID = int(_e("OWNER_ID"))
except ValueError:
    sys.stderr.write("XATO: OWNER_ID faqat raqam bo'lishi kerak (@userinfobot dan oling).\n")
    sys.exit(1)

# Modellar (xohlasangiz Render'da o'zgartirasiz)
MODEL = _e("MODEL", "claude-sonnet-5-5")
FAST_MODEL = _e("FAST_MODEL", "claude-haiku-5-5")

# Ma'lumotlar bazasi: DATABASE_URL (Postgres) bo'lsa o'sha, bo'lmasa SQLite fayl
DATABASE_URL = _e("DATABASE_URL")
DB_PATH = _e("DB_PATH", "data/bot.db")

# Vaqt mintaqasi
try:
    TZ = ZoneInfo(_e("TIMEZONE", "UTC"))
except Exception:
    TZ = ZoneInfo("UTC")

# Webhook
BASE_URL = (_e("BASE_URL") or _e("RENDER_EXTERNAL_URL")).rstrip("/")
WEBHOOK_SECRET = _e("WEBHOOK_SECRET") or hashlib.sha256(("wh:" + BOT_TOKEN).encode()).hexdigest()
PORT = int(_e("PORT", "10000"))

# Xulq-atvor
DEFAULT_MODE = _e("DEFAULT_MODE", "auto")          # auto | draft | off
DEBOUNCE_SECONDS = float(_e("DEBOUNCE_SECONDS", "6"))
PAUSE_MINUTES = int(_e("PAUSE_MINUTES", "30"))     # o'zingiz yozsangiz bot shuncha daqiqa jim turadi
MAX_REPLIES_PER_HOUR = int(_e("MAX_REPLIES_PER_HOUR", "40"))
AI_TAG = _e("AI_TAG")                              # ixtiyoriy: avto-javob oxiriga qo'shiladi, masalan "🤖"
