"""Egasi nomidan xabar yuborish (yozayotgan ko'rinish + o'z-o'zini aks-sadosini aniqlash)."""
import asyncio
import logging
import time

from aiogram.exceptions import TelegramRetryAfter

from utils import norm

log = logging.getLogger("sender")
_recent: dict = {}  # chat_id -> [(norm_text, ts)]


def _register(chat_id, text):
    now = time.time()
    lst = [x for x in _recent.get(chat_id, []) if now - x[1] < 180]
    lst.append((norm(text), now))
    _recent[chat_id] = lst


def consume_echo(chat_id, text) -> bool:
    """Bot o'zi yuborgan xabar qaytib kelsa (business_message sifatida) True qaytaradi."""
    now = time.time()
    n = norm(text)
    lst = [x for x in _recent.get(chat_id, []) if now - x[1] < 180]
    for i, (t, _) in enumerate(lst):
        if t == n:
            lst.pop(i)
            _recent[chat_id] = lst
            return True
    _recent[chat_id] = lst
    return False


async def send_as_owner(bot, chat_id, conn_id, text, typing=True):
    """Matnni (kerak bo'lsa 3 tagacha bo'lib) yuboradi. Yuborilgan qismlar ro'yxatini qaytaradi."""
    parts = [p.strip() for p in (text or "").split("\n\n") if p.strip()][:3]
    if not parts:
        stripped = (text or "").strip()
        parts = [stripped] if stripped else []
    if not parts:
        raise ValueError("Bo'sh xabar yuborib bo'lmaydi")
    sent = []
    for p in parts:
        if typing:
            try:
                await bot.send_chat_action(chat_id=chat_id, action="typing", business_connection_id=conn_id)
            except Exception:  # noqa: BLE001
                pass
            await asyncio.sleep(min(1.0 + len(p) * 0.035, 6.0))
        _register(chat_id, p)
        for attempt in range(3):
            try:
                await bot.send_message(chat_id=chat_id, text=p, business_connection_id=conn_id)
                break
            except TelegramRetryAfter as e:
                log.warning("Flood control: %s soniya kutaman", e.retry_after)
                await asyncio.sleep(e.retry_after + 1)
            except Exception:  # noqa: BLE001
                if attempt == 2:
                    raise
                await asyncio.sleep(1.5 * (attempt + 1))
        sent.append(p)
    return sent
