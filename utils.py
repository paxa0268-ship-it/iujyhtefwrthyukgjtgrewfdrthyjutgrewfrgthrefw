import asyncio
import html
import logging
import re
from datetime import datetime, timezone

import config as cfg

log = logging.getLogger("utils")
_tasks: set = set()


def spawn(coro):
    """Fon vazifasi (garbage collector o'chirib yubormasligi uchun ushlab turiladi)."""
    t = asyncio.create_task(coro)
    _tasks.add(t)

    def _done(task):
        _tasks.discard(task)
        if not task.cancelled() and task.exception():
            log.error("Fon vazifasida xato", exc_info=task.exception())

    t.add_done_callback(_done)
    return t


def esc(s) -> str:
    return html.escape(str(s or ""))


def short(s: str, n: int = 160) -> str:
    s = (s or "").strip().replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def split_text(text: str, limit: int = 3800):
    text = text or ""
    out = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit
        out.append(text[:cut])
        text = text[cut:].lstrip("\n")
    if text:
        out.append(text)
    return out


def fmt_dt(dt) -> str:
    """Bazadagi UTC (naive) vaqtni mahalliy ko'rinishga o'tkazadi."""
    if dt is None:
        return "?"
    loc = dt.replace(tzinfo=timezone.utc).astimezone(cfg.TZ)
    now = datetime.now(cfg.TZ)
    if loc.date() == now.date():
        return loc.strftime("%H:%M")
    return loc.strftime("%d.%m %H:%M")


def now_str() -> str:
    return datetime.now(cfg.TZ).strftime("%A, %d.%m.%Y %H:%M (%Z)")


_URL_ONLY = re.compile(r"^\s*(https?://\S+|www\.\S+)\s*$", re.I)


def good_style_text(t: str) -> bool:
    t = (t or "").strip()
    if not (2 <= len(t) <= 500):
        return False
    if t.startswith("/") or _URL_ONLY.match(t):
        return False
    if t.startswith("[") and t.endswith("]"):
        return False
    return True


def describe_message(m) -> str:
    """Xabarni matnga aylantiradi (rasm, ovoz va h.k. uchun belgi qo'yadi)."""
    txt = m.text or m.caption
    prefix = ""
    if m.photo:
        prefix = "[rasm]"
    elif m.voice:
        prefix = "[ovozli xabar — tinglab bo'lmaydi]"
    elif m.video_note:
        prefix = "[video-xabar — ko'rib bo'lmaydi]"
    elif m.video:
        prefix = "[video]"
    elif m.animation:
        prefix = "[gif]"
    elif m.sticker:
        prefix = f"[stiker {m.sticker.emoji or ''}]".replace(" ]", "]")
    elif m.audio:
        prefix = "[audio]"
    elif m.document:
        prefix = f"[fayl: {m.document.file_name or 'nomsiz'}]"
    elif m.location:
        prefix = "[lokatsiya]"
    elif m.contact:
        prefix = "[kontakt]"
    elif m.poll:
        prefix = "[so'rovnoma]"
    if txt:
        return f"{prefix} {txt}".strip()
    return prefix or "[qo'llab-quvvatlanmaydigan xabar]"
