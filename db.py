"""Ma'lumotlar bazasi (SQLAlchemy Core): Postgres (DATABASE_URL) yoki SQLite."""
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

import config as cfg


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


md = sa.MetaData()

facts = sa.Table(
    "facts", md,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("category", sa.String(40), nullable=False, default="boshqa"),
    sa.Column("content", sa.Text, nullable=False),
    sa.Column("visibility", sa.String(10), nullable=False, default="private"),
    sa.Column("source", sa.String(20), default="owner"),
    sa.Column("created_at", sa.DateTime, default=utcnow),
    sa.Column("updated_at", sa.DateTime, default=utcnow),
)
styles = sa.Table(
    "style_samples", md,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("text", sa.Text, nullable=False),
    sa.Column("source", sa.String(10), default="chat"),  # chat | bot
    sa.Column("created_at", sa.DateTime, default=utcnow),
)
kv = sa.Table(
    "kv", md,
    sa.Column("key", sa.String(64), primary_key=True),
    sa.Column("value", sa.Text),
)
messages = sa.Table(
    "messages", md,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("chat_id", sa.BigInteger, index=True),
    sa.Column("role", sa.String(12)),  # them | owner | bot | assistant
    sa.Column("name", sa.String(120)),
    sa.Column("text", sa.Text),
    sa.Column("created_at", sa.DateTime, default=utcnow),
)
contacts = sa.Table(
    "contacts", md,
    sa.Column("chat_id", sa.BigInteger, primary_key=True, autoincrement=False),
    sa.Column("name", sa.String(160)),
    sa.Column("username", sa.String(80)),
    sa.Column("relation", sa.String(120)),
    sa.Column("notes", sa.Text),
    sa.Column("connection_id", sa.String(120)),
    sa.Column("muted", sa.Boolean, default=False),
    sa.Column("paused_until", sa.DateTime),
    sa.Column("first_seen", sa.DateTime, default=utcnow),
    sa.Column("last_seen", sa.DateTime, default=utcnow),
    sa.Column("msg_count", sa.Integer, default=0),
)
drafts = sa.Table(
    "drafts", md,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("chat_id", sa.BigInteger),
    sa.Column("connection_id", sa.String(120)),
    sa.Column("text", sa.Text),
    sa.Column("status", sa.String(10), default="pending"),
    sa.Column("created_at", sa.DateTime, default=utcnow),
)
notif = sa.Table(
    "notif_map", md,
    sa.Column("msg_id", sa.Integer, primary_key=True, autoincrement=False),
    sa.Column("chat_id", sa.BigInteger),
    sa.Column("created_at", sa.DateTime, default=utcnow),
)
conns = sa.Table(
    "connections", md,
    sa.Column("id", sa.String(120), primary_key=True),
    sa.Column("user_id", sa.BigInteger),
    sa.Column("can_reply", sa.Boolean, default=True),
    sa.Column("is_enabled", sa.Boolean, default=True),
    sa.Column("updated_at", sa.DateTime, default=utcnow),
)
reminders = sa.Table(
    "reminders", md,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("remind_at", sa.DateTime, nullable=False, index=True),
    sa.Column("text", sa.Text, nullable=False),
    sa.Column("done", sa.Boolean, default=False),
    sa.Column("created_at", sa.DateTime, default=utcnow),
)


def _make_engine():
    url = cfg.DATABASE_URL
    if not url:
        d = os.path.dirname(cfg.DB_PATH)
        if d:
            os.makedirs(d, exist_ok=True)
        return create_async_engine(f"sqlite+aiosqlite:///{cfg.DB_PATH}")
    parts = urlsplit(url)
    base = re.sub(r"^postgres(ql)?(\+\w+)?://", "postgresql+asyncpg://", url.split("?")[0])
    local = (parts.hostname or "") in ("localhost", "127.0.0.1")
    args = {"statement_cache_size": 0}
    if not local and "sslmode=disable" not in url:
        args["ssl"] = True
    return create_async_engine(
        base + "?prepared_statement_cache_size=0",
        pool_size=3, max_overflow=2, pool_pre_ping=True, pool_recycle=240,
        connect_args=args,
    )


engine = _make_engine()


async def init():
    async with engine.begin() as c:
        await c.run_sync(md.create_all)


async def close():
    await engine.dispose()


def _d(row):
    return dict(row._mapping) if row is not None else None


# ---------- kv ----------
async def kv_get(key, default=None):
    async with engine.connect() as c:
        r = (await c.execute(sa.select(kv.c.value).where(kv.c.key == key))).first()
    return r[0] if r and r[0] is not None else default


async def kv_set(key, value):
    value = str(value)
    async with engine.begin() as c:
        r = (await c.execute(sa.select(kv.c.key).where(kv.c.key == key))).first()
        if r:
            await c.execute(sa.update(kv).where(kv.c.key == key).values(value=value))
        else:
            await c.execute(sa.insert(kv).values(key=key, value=value))


# ---------- facts ----------
async def add_fact(category, content, visibility="private", source="owner"):
    content = content.strip()
    async with engine.begin() as c:
        r = (await c.execute(sa.select(facts.c.id).where(sa.func.lower(facts.c.content) == content.lower()))).first()
        if r:
            return r[0], False
        res = await c.execute(sa.insert(facts).values(
            category=(category or "boshqa")[:40], content=content,
            visibility=visibility, source=source))
        return res.inserted_primary_key[0], True


async def list_facts(visibility=None, q=None, limit=600):
    stmt = sa.select(facts).order_by(facts.c.id)
    if visibility:
        stmt = stmt.where(facts.c.visibility == visibility)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(sa.or_(sa.func.lower(facts.c.content).like(like),
                                 sa.func.lower(facts.c.category).like(like)))
    async with engine.connect() as c:
        rows = (await c.execute(stmt.limit(limit))).all()
    return [_d(r) for r in rows]


async def get_fact(fid):
    async with engine.connect() as c:
        return _d((await c.execute(sa.select(facts).where(facts.c.id == int(fid)))).first())


async def update_fact(fid, **vals):
    vals["updated_at"] = utcnow()
    async with engine.begin() as c:
        res = await c.execute(sa.update(facts).where(facts.c.id == int(fid)).values(**vals))
    return res.rowcount > 0


async def delete_fact(fid):
    async with engine.begin() as c:
        res = await c.execute(sa.delete(facts).where(facts.c.id == int(fid)))
    return res.rowcount > 0


async def count_facts():
    async with engine.connect() as c:
        rows = (await c.execute(sa.select(facts.c.visibility, sa.func.count()).group_by(facts.c.visibility))).all()
    return {r[0]: r[1] for r in rows}


# ---------- style ----------
async def add_style(text, source="chat"):
    text = text.strip()
    async with engine.begin() as c:
        r = (await c.execute(sa.select(styles.c.id).where(styles.c.text == text).limit(1))).first()
        if r:
            return False
        await c.execute(sa.insert(styles).values(text=text, source=source))
    return True


async def add_styles_bulk(texts, source="chat"):
    """Eskidan yangiga tartibda beriladi; takrorlari qo'shilmaydi."""
    seen, uniq = set(), []
    for t in texts:
        t = t.strip()
        if t and t not in seen:
            seen.add(t)
            uniq.append(t)
    if not uniq:
        return 0
    existing = set()
    async with engine.connect() as c:
        for i in range(0, len(uniq), 200):
            chunk = uniq[i:i + 200]
            rows = (await c.execute(sa.select(styles.c.text).where(styles.c.text.in_(chunk)))).all()
            existing.update(r[0] for r in rows)
    new = [t for t in uniq if t not in existing]
    async with engine.begin() as c:
        for i in range(0, len(new), 200):
            await c.execute(sa.insert(styles), [{"text": t, "source": source, "created_at": utcnow()} for t in new[i:i + 200]])
    return len(new)


async def recent_styles(n, source=None):
    stmt = sa.select(styles.c.text).order_by(styles.c.id.desc()).limit(n)
    if source:
        stmt = stmt.where(styles.c.source == source)
    async with engine.connect() as c:
        rows = (await c.execute(stmt)).all()
    return [r[0] for r in reversed(rows)]


async def styles_after(last_id, limit=80):
    async with engine.connect() as c:
        rows = (await c.execute(sa.select(styles.c.id, styles.c.text).where(styles.c.id > last_id)
                                .order_by(styles.c.id).limit(limit))).all()
    return [(r[0], r[1]) for r in rows]


async def count_styles(source=None):
    stmt = sa.select(sa.func.count()).select_from(styles)
    if source:
        stmt = stmt.where(styles.c.source == source)
    async with engine.connect() as c:
        return (await c.execute(stmt)).scalar() or 0


# ---------- messages ----------
async def add_msg(chat_id, role, name, text):
    async with engine.begin() as c:
        res = await c.execute(sa.insert(messages).values(chat_id=chat_id, role=role, name=(name or "")[:120], text=text))
    return res.inserted_primary_key[0]


async def recent_msgs(chat_id, n=20):
    async with engine.connect() as c:
        rows = (await c.execute(sa.select(messages).where(messages.c.chat_id == chat_id)
                                .order_by(messages.c.id.desc()).limit(n))).all()
    return [_d(r) for r in reversed(rows)]


async def last_msg_id(chat_id):
    async with engine.connect() as c:
        return (await c.execute(sa.select(sa.func.max(messages.c.id)).where(messages.c.chat_id == chat_id))).scalar() or 0


async def count_recent(chat_id, role, minutes=60):
    since = utcnow() - timedelta(minutes=minutes)
    async with engine.connect() as c:
        return (await c.execute(sa.select(sa.func.count()).select_from(messages).where(
            sa.and_(messages.c.chat_id == chat_id, messages.c.role == role, messages.c.created_at >= since)))).scalar() or 0


async def clear_msgs(chat_id):
    async with engine.begin() as c:
        await c.execute(sa.delete(messages).where(messages.c.chat_id == chat_id))


# ---------- contacts ----------
async def upsert_contact(chat_id, name, username, connection_id, inc=False):
    async with engine.begin() as c:
        r = (await c.execute(sa.select(contacts).where(contacts.c.chat_id == chat_id))).first()
        if r:
            vals = {"last_seen": utcnow(), "name": name or r._mapping["name"],
                    "username": username or r._mapping["username"]}
            if connection_id:
                vals["connection_id"] = connection_id
            if inc:
                vals["msg_count"] = (r._mapping["msg_count"] or 0) + 1
            await c.execute(sa.update(contacts).where(contacts.c.chat_id == chat_id).values(**vals))
        else:
            await c.execute(sa.insert(contacts).values(
                chat_id=chat_id, name=name, username=username, connection_id=connection_id,
                muted=False, msg_count=1 if inc else 0, first_seen=utcnow(), last_seen=utcnow()))


async def get_contact(chat_id):
    async with engine.connect() as c:
        return _d((await c.execute(sa.select(contacts).where(contacts.c.chat_id == chat_id))).first())


async def update_contact(chat_id, **vals):
    async with engine.begin() as c:
        res = await c.execute(sa.update(contacts).where(contacts.c.chat_id == chat_id).values(**vals))
    return res.rowcount > 0


async def list_contacts(n=40):
    async with engine.connect() as c:
        rows = (await c.execute(sa.select(contacts).order_by(contacts.c.last_seen.desc()).limit(n))).all()
    return [_d(r) for r in rows]


# ---------- drafts / notif / connections ----------
async def create_draft(chat_id, connection_id, text):
    async with engine.begin() as c:
        res = await c.execute(sa.insert(drafts).values(chat_id=chat_id, connection_id=connection_id, text=text, status="pending"))
    return res.inserted_primary_key[0]


async def get_draft(did):
    async with engine.connect() as c:
        return _d((await c.execute(sa.select(drafts).where(drafts.c.id == int(did)))).first())


async def set_draft(did, **vals):
    async with engine.begin() as c:
        await c.execute(sa.update(drafts).where(drafts.c.id == int(did)).values(**vals))


async def save_notif(msg_id, chat_id):
    async with engine.begin() as c:
        await c.execute(sa.delete(notif).where(notif.c.msg_id == msg_id))
        await c.execute(sa.insert(notif).values(msg_id=msg_id, chat_id=chat_id))


async def get_notif(msg_id):
    async with engine.connect() as c:
        r = (await c.execute(sa.select(notif.c.chat_id).where(notif.c.msg_id == msg_id))).first()
    return r[0] if r else None


async def save_conn(cid, user_id, can_reply, is_enabled):
    async with engine.begin() as c:
        r = (await c.execute(sa.select(conns.c.id).where(conns.c.id == cid))).first()
        vals = dict(user_id=user_id, can_reply=bool(can_reply), is_enabled=bool(is_enabled), updated_at=utcnow())
        if r:
            await c.execute(sa.update(conns).where(conns.c.id == cid).values(**vals))
        else:
            await c.execute(sa.insert(conns).values(id=cid, **vals))


async def get_conn(cid):
    async with engine.connect() as c:
        return _d((await c.execute(sa.select(conns).where(conns.c.id == cid))).first())


async def list_conns():
    async with engine.connect() as c:
        return [_d(r) for r in (await c.execute(sa.select(conns))).all()]


# ---------- eslatmalar ----------
async def add_reminder(remind_at, text):
    async with engine.begin() as c:
        res = await c.execute(sa.insert(reminders).values(remind_at=remind_at, text=text.strip(), done=False))
    return res.inserted_primary_key[0]


async def due_reminders(now, limit=20):
    async with engine.connect() as c:
        rows = (await c.execute(sa.select(reminders).where(
            sa.and_(reminders.c.done.is_(False), reminders.c.remind_at <= now)
        ).order_by(reminders.c.remind_at).limit(limit))).all()
    return [_d(r) for r in rows]


async def mark_reminder_done(rid):
    async with engine.begin() as c:
        await c.execute(sa.update(reminders).where(reminders.c.id == rid).values(done=True))


async def list_pending_reminders(limit=30):
    async with engine.connect() as c:
        rows = (await c.execute(sa.select(reminders).where(reminders.c.done.is_(False))
                                .order_by(reminders.c.remind_at).limit(limit))).all()
    return [_d(r) for r in rows]


async def delete_reminder(rid):
    async with engine.begin() as c:
        res = await c.execute(sa.delete(reminders).where(reminders.c.id == int(rid)))
    return res.rowcount > 0
