import asyncio
import logging

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

import config as cfg
import db
import handlers_others
import handlers_owner
import reminders
from utils import spawn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("main")

bot = Bot(token=cfg.BOT_TOKEN)
dp = Dispatcher()
dp.include_router(handlers_owner.router)   # avval egasi
dp.include_router(handlers_others.router)  # keyin boshqalar

# Faqat egasiga ko'rinadigan to'liq menyu (notanish odamlar boshqa buyruqlarni ko'rmasin)
OWNER_COMMANDS = [
    ("start", "Boshlash"), ("yordam", "Yordam"), ("intervyu", "Men haqimda savollar"),
    ("fakt", "Saqlangan faktlar"), ("sinov", "Qanday javob berishimni sinash"),
    ("rejim", "auto / draft / off"), ("xabar", "Bildirishnomalar"),
    ("kontaktlar", "Kontaktlar"), ("uslub", "Yozish uslubim"), ("holat", "Holat"),
    ("eslatma", "Eslatma qo'yish"), ("eslatmalar", "Faol eslatmalar"),
    ("eksport", "Zaxira nusxa"), ("yangi", "Suhbat tarixini tozalash"),
]
# Notanish odamlar uchun minimal menyu
DEFAULT_COMMANDS = [("start", "Boshlash")]

KEEPALIVE_SECONDS = 600  # 10 daqiqa: Render bepul server uxlab qolmasin (tashqi xizmatsiz)


@dp.errors()
async def on_error(event):
    log.error("Handlerda xato: %s", event.exception, exc_info=event.exception)
    return True


async def _setup_telegram(bot: Bot):
    """Telegram sozlamalari fonda bajariladi: server portni darhol ochadi (Render shuni kutadi)."""
    try:
        await bot.set_my_commands([BotCommand(command=c, description=d) for c, d in DEFAULT_COMMANDS],
                                   scope=BotCommandScopeDefault())
        await bot.set_my_commands([BotCommand(command=c, description=d) for c, d in OWNER_COMMANDS],
                                   scope=BotCommandScopeChat(chat_id=cfg.OWNER_ID))
    except Exception as e:  # noqa: BLE001
        log.error("Buyruqlar menyusini o'rnatib bo'lmadi: %s", e)
    if not cfg.BASE_URL:
        return
    for attempt in range(1, 6):
        try:
            await bot.set_webhook(
                f"{cfg.BASE_URL}/webhook",
                secret_token=cfg.WEBHOOK_SECRET,
                allowed_updates=dp.resolve_used_update_types(),
            )
            log.info("Webhook o'rnatildi: %s/webhook", cfg.BASE_URL)
            return
        except Exception as e:  # noqa: BLE001
            log.error("set_webhook %s-urinish xato: %s (BOT_TOKEN to'g'rimi?)", attempt, e)
            await asyncio.sleep(5)


async def _keepalive():
    """Render bepul servisi ~15 daqiqa jim tursa uxlaydi: shu sabab o'zini-o'zi davriy 'uyg'otib' turadi."""
    if not cfg.BASE_URL:
        return
    await asyncio.sleep(120)
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        while True:
            try:
                async with session.get(f"{cfg.BASE_URL}/health") as r:
                    log.info("Keepalive ping: %s", r.status)
            except Exception as e:  # noqa: BLE001
                log.warning("Keepalive ping xato: %s", e)
            await asyncio.sleep(KEEPALIVE_SECONDS)


async def on_startup(bot: Bot):
    await db.init()
    spawn(_setup_telegram(bot))
    spawn(reminders.loop(bot))
    spawn(_keepalive())


async def on_shutdown(bot: Bot):
    await db.close()
    await bot.session.close()


async def health(_):
    return web.Response(text="ok")


def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    if cfg.BASE_URL:
        app = web.Application()
        app.router.add_get("/", health)
        app.router.add_get("/health", health)
        SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=cfg.WEBHOOK_SECRET).register(app, path="/webhook")
        setup_application(app, dp, bot=bot)
        web.run_app(app, host="0.0.0.0", port=cfg.PORT)
    else:
        log.info("BASE_URL yo'q: polling rejimi (lokal sinov)")

        async def poll():
            await bot.delete_webhook()
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

        asyncio.run(poll())


if __name__ == "__main__":
    main()
