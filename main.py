import asyncio
import logging

from aiogram import types

import database
from handlers import dp

logger = logging.getLogger(__name__)


async def main():
    # Ensure DB tables exist
    await database.create_tables()

    # Automatic backup on startup: create backup if last backup older than threshold days
    try:
        from src.config import DIR
        import os
        import shutil
        from datetime import datetime, timedelta

        BACKUP_DIR = os.path.join(DIR, "backups")
        os.makedirs(BACKUP_DIR, exist_ok=True)

        # Threshold (in days) to create a new backup if none newer than this
        BACKUP_THRESHOLD_DAYS = int(os.environ.get('BACKUP_THRESHOLD_DAYS', '2'))

        db_path = os.path.join(DIR, "shopDB.sqlite")
        create_backup = True

        if os.path.exists(BACKUP_DIR):
            # find newest backup
            backups = [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.endswith('.sqlite')]
            if backups:
                latest = max(backups, key=os.path.getmtime)
                mtime = datetime.fromtimestamp(os.path.getmtime(latest))
                if datetime.now() - mtime < timedelta(days=BACKUP_THRESHOLD_DAYS):
                    create_backup = False

        if create_backup and os.path.exists(db_path):
            ts = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            dest = os.path.join(BACKUP_DIR, f'shopDB_{ts}.sqlite')
            try:
                shutil.copy2(db_path, dest)
                logger.info(f'Backup created: {dest}')
            except Exception as e:
                logger.exception(f'Failed to create backup: {e}')
    except Exception:
        # Don't block startup on backup failures
        logger.exception('Backup check failed')

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    logger.info("Starting bot")

    # await dp.skip_updates() # Commented out to see pending updates if any
    await dp.bot.set_my_commands([
        types.BotCommand("start", "Запуск бота"),
        types.BotCommand("cancel", "Если завис бот")
    ])

    # Настройка сессии с увеличенным таймаутом
    from aiohttp import ClientTimeout, ClientSession, TCPConnector
    
    # Увеличиваем таймаут сессии
    timeout = ClientTimeout(total=60, connect=20, sock_read=20, sock_connect=20)
    
    # Используем ssl=False - это стандартный способ отключить проверку в aiohttp
    connector = TCPConnector(limit=10, ssl=False)
    
    # Подменяем сессию бота
    session = ClientSession(connector=connector, timeout=timeout)
    dp.bot._session = session

    from handlers.callback import main_callback
    logger.info("Загружен handlers.callback.main_callback")

    from handlers.callback import payment_callback
    logger.info("Загружен handlers.callback.payment_callback")
    
    from handlers.callback import balance_callback
    logger.info("Загружен handlers.callback.balance_callback")

    from handlers.callback import order_callback

    import admin_handlers
    logger.info("Загружен admin_handlers")
    
    # Запускаем фоновый чекер СМС
    from bin.checker import start_checker
    asyncio.create_task(start_checker())
    
    await dp.start_polling(dp, allowed_updates=["message", "callback_query", "inline_query", "chat_member", "my_chat_member"])


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(e)
