"""Egasi (siz) bilan shaxsiy chat: o'rgatish, so'rash, sozlash."""
import io
import json
import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import BufferedInputFile, CallbackQuery, Message

import brain
import config as cfg
import db
import importer
import reminders
import sender
from handlers_others import mode, notify_level
from utils import fmt_dt, good_style_text, short, spawn, split_text

log = logging.getLogger("owner")
router = Router(name="owner")
router.message.filter(F.from_user.id == cfg.OWNER_ID, F.chat.type == "private")
router.callback_query.filter(F.from_user.id == cfg.OWNER_ID)

QUESTIONS = [
    "To'liq isming, qanday chaqirishsin (laqabing)?",
    "Qachon va qayerda tug'ilgansan? Hozir qayerda yashaysan?",
    "Qaysi tillarda gaplashasan? Odatda qaysi tilda va qaysi yozuvda (lotin/kirill) yozasan?",
    "Oilangda kimlar bor (ota-ona, aka-uka, turmush o'rtog'i, bolalar)? Ismlari va ular kim ekanini ayt.",
    "Eng yaqin do'stlaring kimlar? Ularning ismi va sen bilan munosabati qanday?",
    "Nima ish qilasan yoki nima o'qiysan? Lavozim/yo'nalish, joy, qancha vaqtdan beri?",
    "Ish yoki o'qish jadvaling qanday? Qachon band bo'lasan, qachon bo'sh?",
    "Qanday ko'nikma va kasbiy yutuqlaring bor?",
    "Hozirgi eng katta maqsadlaring va rejalaring nimalar?",
    "Qiziqishlaring, hobbilaring qaysilar?",
    "Sevimli ovqat, ichimlik, musiqa, film, kitob, sport jamoalaring?",
    "Kun tartibing qanday (necha uyg'onasan, necha yotasan, odatlaring)?",
    "Telefon qilishni yaxshi ko'rasanmi yoki yozishnimi? Xabarlarga odatda qanchada javob berasan?",
    "Notanish odamlarga qanday muomala qilasan? Do'stlarga-chi? Kattalarga-chi (sen/siz)?",
    "Odamlar senga nimani so'rab ko'p yozishadi? Odatda qanday javob berasan?",
    "Qaysi mavzularda hech kimga javob bermasligim kerak (pul, sir, shaxsiy narsalar)? Nimalarni faqat o'zing hal qilasan?",
    "Fikringcha o'zingning eng yaxshi va eng zaif tomonlaring?",
    "Qiyin vaziyatda (janjal, tanqid, bosim) odatda qanday yo'l tutasan?",
    "Hazil qilasanmi? Qanday hazil yoqadi? Qaysi so'z va iboralarni tez-tez ishlatasan?",
    "Qaysi mavzularga qat'iy fikring bor (din, siyosat, pul, oila, ish)? Qisqacha ayt.",
    "Muhim sanalar: tug'ilgan kunlar, yubileylar, doimiy uchrashuvlar?",
    "Salomatlik haqida eslatib qo'yishim kerak bo'lgan narsa bormi (allergiya, dori)? Bu maxfiy saqlanadi.",
    "Moliyaviy odatlaring/obunalaring/kreditlaring haqida eslatma bormi? Bu ham maxfiy saqlanadi.",
    "Yana men bilishim kerak bo'lgan, o'zing haqingdagi muhim narsa nima?",
]

HELP = """🤖 <b>Men-Bot</b>: sening raqamli yordamching

<b>O'rgatish</b>
• Shunchaki yoz: "Men 1999-yilda Samarqandda tug'ilganman" — saqlayman
• /intervyu — savollar bilan o'zing haqingda hammasini so'rayman
• .json fayl yubor — Telegram Desktop'dan eksport qilingan chat (uslubingni o'rganaman)
• Business chatlarda o'zing yozganlaring avtomatik o'rganiladi

<b>So'rash</b>
• "Tug'ilgan kunim qachon?", "Do'stim Alining raqami?" — aniq javob beraman
• /fakt [so'z] — saqlangan faktlar
• /sinov <xabar> — notanish odam shuni yozsa, men qanday javob berishimni ko'rsat

<b>Boshqarish</b>
• /rejim auto|draft|off — avto-javob / avval senga ko'rsat / o'chiq
• /xabar all|important|off — senga bildirishnomalar
• /ochir <id> · /ochiq <id> · /yopiq <id> — faktni o'chirish / boshqalarga ochiq / maxfiy
• /kontaktlar · /kim <chat_id> <kim> — kontaktlar va ularning kimligi
• /uslub [yangila] — yozish uslubing tahlili
• /holat · /eksport · /yangi (suhbat tarixini tozalash)

<b>Eslatmalar</b>
• /eslatma 45 Dori ichish — 45 daqiqadan keyin eslataman
• /eslatma 18:30 Trenajyor zali — bugun (o'tgan bo'lsa ertaga) shu vaqtda
• /eslatmalar — faol eslatmalar ro'yxati
• /eslatma_ochir <id> — eslatmani bekor qilish

<b>Bildirishnomaga reply</b> qilib ko'rsatma yozsang ("ertaga bora olmayman de"), o'sha odamga sening uslubingda yuboraman. "!" bilan boshlasang matnni so'zma-so'z yuboraman."""


# ---------- buyruqlar ----------
@router.message(Command("start"))
async def cmd_start(m: Message):
    if not await db.kv_get("owner_name"):
        await db.kv_set("owner_name", m.from_user.first_name or m.from_user.full_name)
        await brain.save_basic_profile(m.from_user)
    conns = [c for c in await db.list_conns() if c["is_enabled"]]
    biz = ("✅ Business akkaunting ulangan." if conns else
           "ℹ️ Hali Business'ga ulanmagan: Telegram > Sozlamalar > Business > Chat-botlar > shu botni qo'sh.")
    await m.answer(f"Salom, {m.from_user.first_name}! 👋\n{biz}\n\n" + HELP, parse_mode="HTML")


@router.message(Command("yordam", "help"))
async def cmd_help(m: Message):
    await m.answer(HELP, parse_mode="HTML")


@router.message(Command("holat"))
async def cmd_status(m: Message):
    f = await db.count_facts()
    conns = await db.list_conns()
    prof = await db.kv_get("style_profile")
    await m.answer(
        f"📊 Holat\n"
        f"Faktlar: {sum(f.values())} (🔓 {f.get('public', 0)} ochiq, 🔒 {f.get('private', 0)} maxfiy)\n"
        f"Uslub namunalari: {await db.count_styles('chat')} (chatdan) + {await db.count_styles('bot')} (shu chatdan)\n"
        f"Uslub profili: {'bor' if prof else 'hali yo‘q'}\n"
        f"Kontaktlar: {len(await db.list_contacts(1000))}\n"
        f"Business ulanish: {'✅' if any(c['is_enabled'] for c in conns) else '❌'}\n"
        f"Rejim: {await mode()} · Bildirishnoma: {await notify_level()}\n"
        f"Model: {cfg.MODEL}")


@router.message(Command("rejim"))
async def cmd_mode(m: Message, command: CommandObject):
    a = (command.args or "").strip().lower()
    if a not in ("auto", "draft", "off"):
        return await m.answer(f"Hozir: {await mode()}\n/rejim auto — o'zim javob beraman\n/rejim draft — avval senga ko'rsataman, tasdiqlasang yuboraman\n/rejim off — hech kimga javob bermayman (faqat o'rganaman)")
    await db.kv_set("mode", a)
    await m.answer(f"✅ Rejim: {a}")


@router.message(Command("xabar"))
async def cmd_notify(m: Message, command: CommandObject):
    a = (command.args or "").strip().lower()
    if a not in ("all", "important", "off"):
        return await m.answer(f"Hozir: {await notify_level()}\n/xabar all — har bir suhbat haqida\n/xabar important — faqat muhimlari\n/xabar off — faqat qoralama/xatolar")
    await db.kv_set("notify", a)
    await m.answer(f"✅ Bildirishnoma: {a}")


@router.message(Command("fakt"))
async def cmd_facts(m: Message, command: CommandObject):
    rows = await db.list_facts(q=command.args)
    if not rows:
        return await m.answer("Hali fakt yo'q. /intervyu ni bos yoki o'zing haqingda yoz.")
    for chunk in split_text(brain.fmt_facts(rows)):
        await m.answer(chunk)


async def _fid(m, command):
    try:
        return int((command.args or "").strip().lstrip("#"))
    except ValueError:
        await m.answer("Fakt raqamini yoz, masalan: /ochir 12")
        return None


@router.message(Command("ochir"))
async def cmd_del(m: Message, command: CommandObject):
    fid = await _fid(m, command)
    if fid is not None:
        await m.answer("🗑 O'chirildi" if await db.delete_fact(fid) else "Topilmadi")


@router.message(Command("ochiq"))
async def cmd_pub(m: Message, command: CommandObject):
    fid = await _fid(m, command)
    if fid is not None:
        await m.answer("🔓 Endi boshqalarga javob berganda ishlataman" if await db.update_fact(fid, visibility="public") else "Topilmadi")


@router.message(Command("yopiq"))
async def cmd_priv(m: Message, command: CommandObject):
    fid = await _fid(m, command)
    if fid is not None:
        await m.answer("🔒 Maxfiy: faqat senga aytaman" if await db.update_fact(fid, visibility="private") else "Topilmadi")


@router.message(Command("uslub"))
async def cmd_style(m: Message, command: CommandObject):
    if (command.args or "").strip().lower().startswith("yangila"):
        await m.bot.send_chat_action(m.chat.id, "typing")
        await brain.maybe_rebuild_style(force=True)
    prof = await db.kv_get("style_profile")
    n = await db.count_styles()
    if not prof:
        return await m.answer(f"Uslub profili hali tuzilmagan ({n} ta namuna). Business chatlarda yozaver, .json eksport yubor yoki /uslub yangila.")
    for chunk in split_text(f"🎨 Yozish uslubing ({n} ta namuna asosida):\n\n{prof}"):
        await m.answer(chunk)


@router.message(Command("kontaktlar"))
async def cmd_contacts(m: Message):
    rows = await db.list_contacts(30)
    if not rows:
        return await m.answer("Hali hech kim yozmagan.")
    lines = [f"{c['chat_id']} · {c['name']}" + (f" @{c['username']}" if c['username'] else "") +
             f" · {c['relation'] or '?'}" + (" · 🔇" if c['muted'] else "") + f" · {fmt_dt(c['last_seen'])}" for c in rows]
    await m.answer("\n".join(lines) + "\n\nKimligini belgilash: /kim <chat_id> <kim>")


@router.message(Command("kim"))
async def cmd_who(m: Message, command: CommandObject):
    parts = (command.args or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[0].lstrip("-").isdigit():
        return await m.answer("Misol: /kim 123456789 eng yaqin do'stim, unga 'sen' deb yoz")
    ok = await db.update_contact(int(parts[0]), relation=parts[1][:120])
    await m.answer("✅ Saqlandi" if ok else "Bunday kontakt topilmadi (/kontaktlar)")


@router.message(Command("sinov"))
async def cmd_test(m: Message, command: CommandObject):
    if not command.args:
        return await m.answer("Misol: /sinov Salom, ertaga uchrashamizmi?")
    await m.bot.send_chat_action(m.chat.id, "typing")
    c = {"name": "Sinov odam", "username": None, "relation": None, "notes": None, "msg_count": 0, "first_seen": db.utcnow()}
    hist = [{"id": 0, "role": "them", "name": "Sinov odam", "text": command.args, "created_at": db.utcnow()}]
    try:
        d = await brain.decide(c, hist)
    except Exception as e:  # noqa: BLE001
        return await m.answer(f"⚠️ Xato: {short(str(e), 300)}")
    await m.answer(f"🧠 {d.get('analysis')}\n\n" + (f"✍️ Javobim:\n{d['reply']}" if d.get("should_reply") and d.get("reply")
                                                   else f"⏸ Javob bermas edim. {d.get('notify_reason') or ''}"))


@router.message(Command("eksport"))
async def cmd_export(m: Message):
    data = {"facts": await db.list_facts(), "style_profile": await db.kv_get("style_profile"),
            "style_samples": await db.recent_styles(300)}
    raw = json.dumps(data, ensure_ascii=False, indent=2, default=str).encode()
    await m.answer_document(BufferedInputFile(raw, "xotira.json"), caption="💾 Zaxira nusxa")


@router.message(Command("yangi"))
async def cmd_new(m: Message):
    await db.clear_msgs(cfg.OWNER_ID)
    await m.answer("🧹 Suhbat tarixi tozalandi (xotira saqlanib qoldi).")


# ---------- eslatmalar ----------
@router.message(Command("eslatma"))
async def cmd_remind(m: Message, command: CommandObject):
    parts = (command.args or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        return await m.answer(
            "Misol:\n/eslatma 45 Dori ichish — 45 daqiqadan keyin\n/eslatma 18:30 Trenajyor zali — bugun shu vaqtda")
    when = reminders.parse_when(parts[0])
    if not when:
        return await m.answer("Vaqtni tushunmadim. Daqiqa soni ('45') yoki 'SOAT:DAQIQA' ('18:30') ko'rinishida yoz.")
    rid = await db.add_reminder(when, parts[1].strip())
    await m.answer(f"⏰ #{rid} eslatma qo'yildi — {fmt_dt(when)} da eslataman.")


@router.message(Command("eslatmalar"))
async def cmd_reminders(m: Message):
    rows = await db.list_pending_reminders()
    if not rows:
        return await m.answer("Hali faol eslatma yo'q. Misol: /eslatma 45 Dori ichish")
    lines = [f"#{r['id']} · {fmt_dt(r['remind_at'])} · {r['text']}" for r in rows]
    await m.answer("\n".join(lines) + "\n\nBekor qilish: /eslatma_ochir <id>")


@router.message(Command("eslatma_ochir"))
async def cmd_remind_del(m: Message, command: CommandObject):
    fid = await _fid(m, command)
    if fid is not None:
        await m.answer("🗑 Bekor qilindi" if await db.delete_reminder(fid) else "Bunday eslatma topilmadi")


# ---------- intervyu ----------
async def _ask_next(m: Message):
    idx = int(await db.kv_get("iv_idx", "0"))
    if idx >= len(QUESTIONS):
        await db.kv_set("iv_active", "0")
        return await m.answer("🎉 Intervyu tugadi! /fakt bilan ko'r, /sinov bilan tekshir.")
    await m.answer(f"({idx + 1}/{len(QUESTIONS)}) {QUESTIONS[idx]}\n\n/keyingi — o'tkazish · /tugat — to'xtatish")


@router.message(Command("intervyu"))
async def cmd_interview(m: Message):
    await db.kv_set("iv_active", "1")
    await m.answer("Boshladik! Har bir savolga o'z so'zlaring bilan javob ber, hammasini eslab qolaman.")
    await _ask_next(m)


@router.message(Command("keyingi"))
async def cmd_skip(m: Message):
    if await db.kv_get("iv_active") != "1":
        return await m.answer("Intervyu yoqilmagan: /intervyu")
    await db.kv_set("iv_idx", int(await db.kv_get("iv_idx", "0")) + 1)
    await _ask_next(m)


@router.message(Command("tugat"))
async def cmd_stop(m: Message):
    await db.kv_set("iv_active", "0")
    await m.answer("Intervyu to'xtatildi. Davom ettirish: /intervyu")


# ---------- fayl (chat eksporti) ----------
@router.message(F.document)
async def on_document(m: Message):
    d = m.document
    if not (d.file_name or "").lower().endswith(".json"):
        return await m.answer("Faqat Telegram Desktop eksport qilgan .json faylni qabul qilaman.")
    if d.file_size and d.file_size > 19 * 1024 * 1024:
        return await m.answer("Fayl 20 MB dan katta. Bitta chatni alohida eksport qiling.")
    await m.answer("📥 Fayl qabul qilindi, o'qiyapman (bir necha daqiqa ketishi mumkin)...")
    buf = io.BytesIO()
    await m.bot.download(d, destination=buf)
    spawn(importer.run_import(m.bot, m.chat.id, buf.getvalue(), cfg.OWNER_ID))


# ---------- erkin matn ----------
def make_executor(bot):
    async def run(name, a):
        if name == "remember_facts":
            added, upd = await brain.apply_facts(a.get("facts", []), "owner")
            return f"saqlandi: {added} yangi, {upd} yangilandi"
        if name == "forget_fact":
            return "o'chirildi" if await db.delete_fact(int(a["fact_id"])) else "topilmadi"
        if name == "set_fact_visibility":
            return "ok" if await db.update_fact(int(a["fact_id"]), visibility=a["visibility"]) else "topilmadi"
        if name == "update_contact":
            vals = {k: a[k] for k in ("relation", "notes", "muted") if k in a}
            return "ok" if vals and await db.update_contact(int(a["chat_id"]), **vals) else "topilmadi yoki o'zgarish yo'q"
        if name == "send_to_contact":
            c = await db.get_contact(int(a["chat_id"]))
            if not c:
                return "kontakt topilmadi"
            await sender.send_as_owner(bot, c["chat_id"], c["connection_id"], a["text"])
            await db.add_msg(c["chat_id"], "bot", "ME", a["text"])
            return "yuborildi"
        return "noma'lum vosita"
    return run


async def _send_instruction(m: Message, chat_id: int, text: str):
    c = await db.get_contact(chat_id)
    if not c:
        return await m.answer("Bu kontakt bazada yo'q.")
    await m.bot.send_chat_action(m.chat.id, "typing")
    if text.startswith("!"):
        out = text[1:].strip()
    else:
        hist = await db.recent_msgs(chat_id, 16)
        out = await brain.compose_for_instruction(c, hist, text)
    if not out:
        return await m.answer("Matn chiqmadi, qayta yozing.")
    try:
        await sender.send_as_owner(m.bot, chat_id, c["connection_id"], out)
    except Exception as e:  # noqa: BLE001
        return await m.answer(f"⚠️ Yuborib bo'lmadi: {short(str(e), 250)}")
    await db.add_msg(chat_id, "bot", "ME", out)
    await m.answer(f"✅ {c['name']}ga yuborildi:\n{out}")


@router.message(F.text)
async def on_text(m: Message):
    text = m.text.strip()
    if text.startswith("/"):
        return await m.answer("Noma'lum buyruq. /yordam")
    if m.reply_to_message:
        chat_id = await db.get_notif(m.reply_to_message.message_id)
        if chat_id:
            return await _send_instruction(m, chat_id, text)
    if good_style_text(text) and not text.endswith("?"):
        await db.add_style(text, "bot")
    await m.bot.send_chat_action(m.chat.id, "typing")
    try:
        if await db.kv_get("iv_active") == "1":
            idx = int(await db.kv_get("iv_idx", "0"))
            if idx < len(QUESTIONS):
                existing = brain.fmt_facts(await db.list_facts())
                items = await brain.llm.extract_facts(existing, f"Interview. Question asked: {QUESTIONS[idx]}", text)
                added, upd = await brain.apply_facts(items, "interview")
                await db.kv_set("iv_idx", idx + 1)
                await m.answer(f"✅ {added + upd} ta fakt saqlandi.")
                return await _ask_next(m)
        reply = await brain.run_owner_agent(text, make_executor(m.bot))
    except Exception as e:  # noqa: BLE001
        log.exception("owner xatosi")
        return await m.answer(f"⚠️ Xatolik: {short(str(e), 300)}\nAPI kalit/modelni tekshiring.")
    for chunk in split_text(reply):
        await m.answer(chunk)
    spawn(_bg_learn())


async def _bg_learn():
    try:
        await brain.maybe_rebuild_style()
        await brain.maybe_auto_learn()
    except Exception:  # noqa: BLE001
        log.exception("o'rganish xatosi")


@router.message()
async def on_other(m: Message):
    await m.answer("Hozircha matn va .json (chat eksporti) qabul qilaman.")


# ---------- tugmalar ----------
@router.callback_query(F.data.startswith("dr:"))
async def cb_draft(cb: CallbackQuery):
    _, act, did = cb.data.split(":")
    d = await db.get_draft(did)
    if not d or d["status"] != "pending":
        return await cb.answer("Bu qoralama allaqachon hal qilingan.", show_alert=True)
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:  # noqa: BLE001
        pass
    if act == "x":
        await db.set_draft(did, status="skipped")
        return await cb.answer("Bekor qilindi")
    if act == "s":
        try:
            await sender.send_as_owner(cb.bot, d["chat_id"], d["connection_id"], d["text"])
        except Exception as e:  # noqa: BLE001
            return await cb.answer(f"Yuborilmadi: {short(str(e), 150)}", show_alert=True)
        await db.set_draft(did, status="sent")
        await db.add_msg(d["chat_id"], "bot", "ME", d["text"])
        await cb.answer("Yuborildi ✅")
        return await cb.message.reply("✅ Yuborildi")
    if act == "r":
        await db.set_draft(did, status="skipped")
        c = await db.get_contact(d["chat_id"])
        hist = await db.recent_msgs(d["chat_id"], 16)
        new = await brain.compose_for_instruction(c, hist, "Oxirgi xabarlarga javobni boshqacha, yangi variantda yoz (avvalgisi: " + d["text"] + ")")
        did2 = await db.create_draft(d["chat_id"], d["connection_id"], new)
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Yubor", callback_data=f"dr:s:{did2}"),
            InlineKeyboardButton(text="🔄 Boshqacha", callback_data=f"dr:r:{did2}"),
            InlineKeyboardButton(text="❌", callback_data=f"dr:x:{did2}")]])
        msg = await cb.message.reply(f"📝 Yangi variant:\n{new}", reply_markup=kb)
        await db.save_notif(msg.message_id, d["chat_id"])
        await cb.answer()


@router.callback_query(F.data.startswith("mu:"))
async def cb_mute(cb: CallbackQuery):
    chat_id = int(cb.data.split(":")[1])
    c = await db.get_contact(chat_id)
    if not c:
        return await cb.answer("Kontakt topilmadi")
    new = not c["muted"]
    await db.update_contact(chat_id, muted=new)
    await cb.answer(("🔇 Bu odamga avto-javob o'chirildi" if new else "🔊 Avto-javob yoqildi"), show_alert=True)
