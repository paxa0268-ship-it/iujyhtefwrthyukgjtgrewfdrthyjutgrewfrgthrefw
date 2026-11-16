"""Eslatmalar: vaqti kelganlarini tekshirib, egasiga xabar yuboradi."""
import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone

import config as cfg
import db

log = logging.getLogger("reminders")
CHECK_SECONDS = 20

_MIN_RE = re.compile(r"^\d{1,5}$")
_HHMM_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def parse_when(raw: str):
    """'45' -> 45 daqiqadan keyin. 'HH:MM' -> bugun shu mahalliy vaqtda (o'tgan bo'lsa ertaga). Tushunarsiz bo'lsa None."""
    raw = (raw or "").strip()
    if _MIN_RE.match(raw):
        mins = int(raw)
        if mins <= 0 or mins > 44640:  # 31 kungacha
            return None
        return db.utcnow() + timedelta(minutes=mins)
    m = _HHMM_RE.match(raw)
    if m:
        now_local = datetime.now(cfg.TZ)
        target = now_local.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
        if target <= now_local:
            target += timedelta(days=1)
        return target.astimezone(timezone.utc).replace(tzinfo=None)
    return None


async def loop(bot):
    """Fonda doimiy aylanib, muddati kelgan eslatmalarni yuboradi (server qayta ishga tushsa ham, bazadagilar saqlanib qoladi)."""
    while True:
        try:
            due = await db.due_reminders(db.utcnow())
            for r in due:
                try:
                    await bot.send_message(cfg.OWNER_ID, f"⏰ Eslatma: {r['text']}")
                except Exception:  # noqa: BLE001
                    log.exception("Eslatmani yuborib bo'lmadi (#%s)", r["id"])
                await db.mark_reminder_done(r["id"])
        except Exception:  # noqa: BLE001
            log.exception("Eslatmalar siklida xato")
        await asyncio.sleep(CHECK_SECONDS)
