"""Boshqa odamlar yozganda: tahlil -> javob (yoki qoralama) -> egasiga xabar."""
import asyncio
import logging
from collections import OrderedDict
from datetime import timedelta

from aiogram import F, Router
from aiogram.types import BusinessConnection, InlineKeyboardButton, InlineKeyboardMarkup, Message

import brain
import config as cfg
import db
import sender
from utils import describe_message, esc, good_style_text, short, spawn

log = logging.getLogger("others")
router = Router(name="others")

_pending: dict[int, asyncio.Task] = {}
_locks: dict[int, asyncio.Lock] = {}
_seen: "OrderedDict[tuple, bool]" = OrderedDict()


def _dup(key) -> bool:
    if key in _seen:
        return True
    _seen[key] = True
    if len(_seen) > 2000:
        _seen.popitem(last=False)
    return False


def _lock(chat_id) -> asyncio.Lock:
    return _locks.setdefault(chat_id, asyncio.Lock())


async def mode() -> str:
    return await db.kv_get("mode", cfg.DEFAULT_MODE)


async def notify_level() -> str:
    return await db.kv_get("notify", "all")


def _can_reply(conn) -> bool:
    r = getattr(conn, "rights", None)
    if r is not None and hasattr(r, "can_reply"):
        return bool(r.can_reply)
    return bool(getattr(conn, "can_reply", True))


# ---------- ulanish ----------
@router.business_connection()
async def on_connection(conn: BusinessConnection, bot):
    if conn.user.id != cfg.OWNER_ID:
        log.warning("Begona odam botni Business'ga ulamoqchi bo'ldi: %s", conn.user.id)
        return
    await db.save_conn(conn.id, conn.user.id, _can_reply(conn), conn.is_enabled)
    if conn.is_enabled:
        txt = "✅ Business akkauntingizga ulandim." + ("" if _can_reply(conn) else
              "\n⚠️ Lekin xabar yozish huquqi yo'q: Telegram > Sozlamalar > Business > Chat-botlar > botni tanlab 'Xabarlarga javob berish' ni yoqing.")
    else:
        txt = "⛔️ Business ulanishi o'chirildi."
    await bot.send_message(cfg.OWNER_ID, txt)


async def ensure_conn(bot, conn_id):
    c = await db.get_conn(conn_id)
    if c:
        return c
    try:
        bc = await bot.get_business_connection(conn_id)
    except Exception:  # noqa: BLE001
        return None
    await db.save_conn(bc.id, bc.user.id, _can_reply(bc), bc.is_enabled)
    return await db.get_conn(conn_id)


# ---------- kiruvchi xabarlar ----------
@router.business_message()
async def on_business(m: Message, bot):
    if not m.business_connection_id or not m.from_user:
        return
    conn = await ensure_conn(bot, m.business_connection_id)
    # Faqat egasining ulanishi qabul qilinadi (begona odam API pulingizni sarflay olmasin)
    if not conn or conn["user_id"] != cfg.OWNER_ID or not conn["is_enabled"]:
        return
    if m.from_user.id == conn["user_id"]:
        await owner_outgoing(m)
    elif not m.from_user.is_bot:
        await incoming(m, bot, m.business_connection_id, direct=False)


@router.message(F.chat.type == "private", F.from_user.id != cfg.OWNER_ID)
async def on_direct(m: Message, bot):
    if not m.from_user or m.from_user.is_bot:
        return
    if (m.text or "").startswith("/start"):
        name = await brain.owner_name()
        await m.answer(f"Salom! Men {name}ning yordamchisiman. Nima haqida gaplashamiz?")
        await db.upsert_contact(m.chat.id, m.from_user.full_name, m.from_user.username, None)
        return
    await incoming(m, bot, None, direct=True)


async def owner_outgoing(m: Message):
    """Egasi shu chatda o'zi yozdi: uslub namunasi + bot vaqtincha jim turadi."""
    text = describe_message(m)
    chat_id = m.chat.id
    if sender.consume_echo(chat_id, text):
        return
    if _dup((chat_id, m.message_id)):
        return
    t = _pending.pop(chat_id, None)
    if t:
        t.cancel()
    await db.upsert_contact(chat_id, m.chat.full_name, m.chat.username, m.business_connection_id)
    await db.add_msg(chat_id, "owner", "ME", text)
    await db.update_contact(chat_id, paused_until=db.utcnow() + timedelta(minutes=cfg.PAUSE_MINUTES))
    raw = m.text or m.caption or ""
    if good_style_text(raw):
        await db.add_style(raw, "chat")
        spawn(_learn())


async def _learn():
    try:
        await brain.maybe_rebuild_style()
        await brain.maybe_auto_learn()
    except Exception:  # noqa: BLE001
        log.exception("o'rganishda xato")


async def incoming(m: Message, bot, conn_id, direct: bool):
    if _dup((m.chat.id, m.message_id)):
        return
    u = m.from_user
    text = describe_message(m)
    await db.upsert_contact(m.chat.id, u.full_name, u.username, conn_id, inc=True)
    await db.add_msg(m.chat.id, "them", u.full_name, text)
    c = await db.get_contact(m.chat.id)
    if await mode() == "off" or c["muted"]:
        return
    if c["paused_until"] and c["paused_until"] > db.utcnow():
        return  # egasi o'zi gaplashyapti
    t = _pending.pop(m.chat.id, None)
    if t:
        t.cancel()
    _pending[m.chat.id] = spawn(_delayed(bot, m.chat.id, conn_id, direct))


async def _delayed(bot, chat_id, conn_id, direct):
    try:
        await asyncio.sleep(cfg.DEBOUNCE_SECONDS)
    except asyncio.CancelledError:
        return
    if _pending.get(chat_id) is asyncio.current_task():
        _pending.pop(chat_id, None)
    async with _lock(chat_id):
        try:
            await process_chat(bot, chat_id, conn_id, direct)
        except Exception:  # noqa: BLE001
            log.exception("process_chat xatosi")


async def process_chat(bot, chat_id, conn_id, direct):
    c = await db.get_contact(chat_id)
    if not c or c["muted"] or (c["paused_until"] and c["paused_until"] > db.utcnow()):
        return
    hist = await db.recent_msgs(chat_id, 24)
    if not hist or hist[-1]["role"] != "them":
        return
    last_id = hist[-1]["id"]

    if await db.count_recent(chat_id, "bot", 60) >= cfg.MAX_REPLIES_PER_HOUR:
        key = f"ratewarn:{chat_id}"
        if int(await db.kv_get(key, "0")) < int(db.utcnow().timestamp()) - 3600:
            await db.kv_set(key, int(db.utcnow().timestamp()))
            await bot.send_message(cfg.OWNER_ID, f"⚠️ {c['name']} bilan chatda soatlik javob limiti tugadi, to'xtatdim.")
        return

    try:
        d = await brain.decide(c, hist, direct)
    except Exception as e:  # noqa: BLE001
        log.exception("decide xatosi")
        await bot.send_message(cfg.OWNER_ID, f"⚠️ {c['name']} xabariga javob tayyorlashda xato: {short(str(e), 200)}")
        return

    if await db.last_msg_id(chat_id) != last_id:
        return  # shu orada yangi xabar keldi yoki egasi yozdi — keyingi aylanish hal qiladi

    reply = (d.get("reply") or "").strip()
    should = bool(d.get("should_reply")) and bool(reply)
    md = await mode()
    sent, draft_id, err = None, None, None
    if should and md == "auto":
        out = reply + (f" {cfg.AI_TAG}" if cfg.AI_TAG else "")
        try:
            await sender.send_as_owner(bot, chat_id, conn_id, out)
            await db.add_msg(chat_id, "bot", "ME", reply)
            sent = reply
        except Exception as e:  # noqa: BLE001
            log.exception("yuborishda xato")
            err = str(e)
    elif should and md == "draft":
        draft_id = await db.create_draft(chat_id, conn_id, reply)

    upd = {}
    if d.get("note_update"):
        old = c.get("notes") or ""
        upd["notes"] = (old + "; " if old else "") + d["note_update"].strip()
        upd["notes"] = upd["notes"][-700:]
    if d.get("relation_guess") and not c.get("relation"):
        upd["relation"] = "~" + d["relation_guess"].strip()[:100]
    if upd:
        await db.update_contact(chat_id, **upd)

    level = await notify_level()
    important = d.get("notify_owner") or d.get("urgency") == "high" or (not sent and not draft_id)
    if draft_id or err or level == "all" or (level == "important" and important):
        await notify_owner(bot, c, trailing_text(hist), d, sent, draft_id, err)


def trailing_text(hist):
    return "\n".join(h["text"] for h in brain.trailing_them(hist))


async def notify_owner(bot, c, incoming_text, d, sent, draft_id, err):
    uname = f" @{c['username']}" if c.get("username") else ""
    lines = [f"✉️ <b>{esc(c['name'])}</b>{esc(uname)}" + (f" · <i>{esc(c['relation'])}</i>" if c.get("relation") else ""),
             esc(short(incoming_text, 600)), "", f"🧠 {esc(d.get('analysis'))}"]
    if d.get("urgency") == "high":
        lines.append("🔥 Shoshilinch")
    if sent:
        lines += ["", f"✅ <b>Javob yuborildi:</b>\n{esc(sent)}"]
    elif draft_id:
        lines += ["", f"📝 <b>Taklif qilingan javob:</b>\n{esc(d.get('reply'))}"]
    else:
        lines += ["", "⏸ Javob bermadim" + (f": {esc(d.get('notify_reason'))}" if d.get("notify_reason") else "")]
    if err:
        lines.append(f"⚠️ Yuborib bo'lmadi: {esc(short(err, 200))}")
    lines.append("\n<i>Shu xabarga reply qilib ko'rsatma yozsangiz, men o'zingiz nomingizdan yuboraman (\"!\" bilan boshlasangiz so'zma-so'z).</i>")
    rows = []
    if draft_id:
        rows.append([InlineKeyboardButton(text="✅ Yubor", callback_data=f"dr:s:{draft_id}"),
                     InlineKeyboardButton(text="🔄 Boshqacha", callback_data=f"dr:r:{draft_id}"),
                     InlineKeyboardButton(text="❌", callback_data=f"dr:x:{draft_id}")])
    rows.append([InlineKeyboardButton(text="🔇 Bu chatni o'chir/yoq", callback_data=f"mu:{c['chat_id']}")])
    msg = await bot.send_message(cfg.OWNER_ID, "\n".join(lines), parse_mode="HTML",
                                 reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await db.save_notif(msg.message_id, c["chat_id"])
    return msg
