import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Загружаем обработчики...")
print("Загружаем обработчики...")

from handlers.message import dp
logger.info("Загружен handlers.message")
print("Загружен handlers.message")

from handlers.callback import dp
logger.info("Загружен handlers.callback")
print("Загружен handlers.callback")

from handlers.callback.main_callback import dp
logger.info("Загружен handlers.callback.main_callback")
print("Загружен handlers.callback.main_callback")

from handlers.callback.payment_callback import dp
logger.info("Загружен handlers.callback.payment_callback")
print("Загружен handlers.callback.payment_callback")

from handlers.callback.order_callback import dp
logger.info("Загружен handlers.callback.order_callback")
print("Загружен handlers.callback.order_callback")

from handlers.error import dp
logger.info("Загружен handlers.error")
print("Загружен handlers.error")

from handlers.inline import dp
logger.info("Загружен handlers.inline")
print("Загружен handlers.inline")

logger.info("Все обработчики загружены!")
print("Все обработчики загружены!")

__all__ = ["dp"]
