"""Telegram Desktop eksporti (result.json) dan egasining yozish uslubi va faktlarini o'rganish."""
import json
import logging

import brain
import db
from utils import good_style_text

log = logging.getLogger("importer")


def _flat(t) -> str:
    if isinstance(t, str):
        return t
    if isinstance(t, list):
        return "".join(x if isinstance(x, str) else x.get("text", "") for x in t)
    return ""


def parse_export(raw: bytes, owner_id: int):
    data = json.loads(raw.decode("utf-8", errors="ignore"))
    if isinstance(data.get("chats"), dict):
        chats = data["chats"].get("list", [])
    elif "messages" in data:
        chats = [data]
    else:
        chats = []
    out = []
    for ch in chats:
        msgs = []
        for m in ch.get("messages", []):
            if m.get("type") != "message":
                continue
            txt = _flat(m.get("text")).strip()
            if not txt:
                continue
            mine = str(m.get("from_id", "")) == f"user{owner_id}"
            msgs.append((mine, m.get("from") or "?", txt))
        out.append({"name": ch.get("name") or "?", "type": ch.get("type", ""), "messages": msgs})
    return out


async def run_import(bot, chat_id, raw: bytes, owner_id: int):
    async def say(t):
        await bot.send_message(chat_id, t)

    try:
        chats = parse_export(raw, owner_id)
    except Exception as e:  # noqa: BLE001
        await say(f"❌ Faylni o'qib bo'lmadi: {e}\nTelegram Desktop > Export chat history > format: JSON bo'lsin.")
        return
    mine = [t for ch in chats for (m, _, t) in ch["messages"] if m and good_style_text(t)]
    if not mine:
        await say("❌ Faylda sizning xabarlaringiz topilmadi (from_id mos kelmadi). Eksportni o'z akkauntingizdan qilganingizni tekshiring.")
        return
    added = await db.add_styles_bulk(mine[-1500:], "chat")
    await say(f"📥 {len(chats)} ta chat o'qildi. Sizning {len(mine)} ta xabaringiz topildi, {added} tasi yangi uslub namunasi sifatida saqlandi.\n⏳ Endi faktlarni ajratib olaman...")

    ranked = sorted([c for c in chats if c["type"] in ("personal_chat", "private_group", "private_supergroup", "saved_messages")],
                    key=lambda c: sum(1 for m in c["messages"] if m[0]), reverse=True)
    ranked = [c for c in ranked if sum(1 for m in c["messages"] if m[0]) >= 8][:5]
    total_added = total_upd = 0
    for ch in ranked:
        lines = [("MEN" if m else n) + ": " + t[:300].replace("\n", " ") for (m, n, t) in ch["messages"][-120:]]
        text = "\n".join(lines)[-8000:]
        try:
            existing = brain.fmt_facts(await db.list_facts())
            items = await brain.llm.extract_facts(existing, f"Chat export between the owner (MEN) and '{ch['name']}'. Extract durable facts about the owner and who this person is to him.", text)
            a, u = await brain.apply_facts(items, "import")
            total_added += a
            total_upd += u
        except Exception:  # noqa: BLE001
            log.exception("import extract xatosi")
    try:
        await brain.maybe_rebuild_style(force=True)
    except Exception:  # noqa: BLE001
        log.exception("style xatosi")
    await say(f"✅ Import tugadi: {total_added} ta yangi fakt, {total_upd} ta yangilandi, uslub profili yangilandi.\nBarchasi 🔒 yopiq (maxfiy) bo'lishi mumkin — /fakt bilan ko'rib, kerakligini /ochiq <id> qiling.")
