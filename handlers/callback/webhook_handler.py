"""
Обработчик webhook'ов от CryptoBot для автоматической обработки платежей
"""

import json
import logging
from aiohttp import web
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import database
from bin.strings import get_cheque_num, get_now_date
from src.config import TOKEN

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем экземпляр бота для отправки сообщений
bot = Bot(token=TOKEN)


async def handle_cryptobot_webhook(request):
    """
    Обработчик webhook'ов от CryptoBot
    """
    try:
        # Получаем данные из webhook'а
        data = await request.json()
        logger.info(f"Получен webhook от CryptoBot: {data}")
        
        # Проверяем тип события
        if data.get("type") == "invoice_paid":
            # Обрабатываем успешную оплату
            await process_paid_invoice(data.get("payload", {}))
        
        # Отвечаем OK
        return web.Response(text="OK", status=200)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке webhook: {e}")
        return web.Response(text="Error", status=500)


async def process_paid_invoice(payload):
    """
    Обработка успешной оплаты инвойса
    """
    try:
        invoice_id = payload.get("invoice_id")
        if not invoice_id:
            logger.error("Не найден invoice_id в webhook")
            return
        
        logger.info(f"Обрабатываем оплаченный инвойс: {invoice_id}")
        
        # Ищем данные о платеже в БД
        payment_data = await find_payment_by_invoice_id(invoice_id)
        if not payment_data:
            logger.error(f"Не найдены данные о платеже для инвойса {invoice_id}")
            return
        
        # Получаем данные о товаре
        item_data = await database.get_item(payment_data['item_id'])
        if not item_data:
            logger.error(f"Товар не найден: {payment_data['item_id']}")
            return
        
        # Формируем данные покупки
        purchase_data = {
            'user_id': payment_data['user_id'],
            'item_id': payment_data['item_id'],
            'item_name': payment_data['item_name'],
            'count': payment_data['count'],
            'amount': payment_data['amount'],
            'date': get_now_date()
        }
        
        # Генерируем чек
        cheque = get_cheque_num()
        purchase_data['cheque'] = cheque
        
        # Записываем покупку в БД
        sale_id = await database.add_buy(purchase_data)
        logger.info(f"Покупка записана в БД с ID: {sale_id}")
        
        # Получаем данные товара
        item_data_list = await database.get_item_data(payment_data['item_id'], payment_data['count'], True)
        logger.info(f"Получены данные товара: {len(item_data_list) if item_data_list else 0} записей")
        
        # Записываем данные проданного товара
        await database.add_sold_item_data(sale_id, item_data_list)
        
        # Отправляем сообщение об успешной оплате
        success_message = f"✅ Оплата прошла успешно!\n\n" \
                         f"🆔 Чек: {cheque}\n" \
                         f"📦 Товар: {purchase_data['item_name']}\n" \
                         f"💰 Сумма: {purchase_data['amount']} руб.\n\n" \
                         f"📱 Данные товара:\n\n"
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main"))
        
        await bot.send_message(payment_data['user_id'], success_message, reply_markup=keyboard)
        
        # Отправляем файлы с данными товара
        for item in item_data_list:
            file_path = item.data if hasattr(item, 'data') else item[2]  # Путь к файлу
            try:
                # Проверяем, существует ли файл
                import os
                if os.path.exists(file_path):
                    # Определяем тип файла по расширению
                    if file_path.endswith('.txt'):
                        with open(file_path, 'rb') as file:
                            await bot.send_document(payment_data['user_id'], file, caption=f"📄 {os.path.basename(file_path)}")
                    elif file_path.endswith(('.jpg', '.jpeg', '.png')):
                        with open(file_path, 'rb') as file:
                            await bot.send_photo(payment_data['user_id'], file, caption=f"🖼️ {os.path.basename(file_path)}")
                    elif file_path.endswith('.mp4'):
                        with open(file_path, 'rb') as file:
                            await bot.send_video(payment_data['user_id'], file, caption=f"🎥 {os.path.basename(file_path)}")
                    else:
                        # Для других типов файлов отправляем как документ
                        with open(file_path, 'rb') as file:
                            await bot.send_document(payment_data['user_id'], file, caption=f"📎 {os.path.basename(file_path)}")
                else:
                    await bot.send_message(payment_data['user_id'], f"❌ Файл не найден: {file_path}")
            except Exception as file_error:
                logger.error(f"Ошибка при отправке файла {file_path}: {file_error}")
                await bot.send_message(payment_data['user_id'], f"❌ Ошибка при отправке файла: {os.path.basename(file_path)}")
        
        # Отправляем финальное сообщение
        await bot.send_message(payment_data['user_id'], "🎉 Спасибо за покупку!", reply_markup=keyboard)
        
        logger.info(f"Товар успешно выдан пользователю {payment_data['user_id']}")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке оплаченного инвойса: {e}")


async def find_payment_by_invoice_id(invoice_id):
    """
    Поиск данных о платеже по ID инвойса
    """
    from sqlalchemy import select
    from src.database_models import Payment
    from database import async_session
    
    try:
        async with async_session() as session:
             result = await session.execute(select(Payment).where(Payment.invoice_id == str(invoice_id)))
             payment = result.scalar_one_or_none()
             
             if payment:
                 return {
                    'user_id': payment.user_id,
                    'invoice_id': payment.invoice_id,
                    'item_id': payment.item_id,
                    'item_name': payment.item_name,
                    'count': payment.count,
                    'amount': payment.amount,
                    'date': payment.date
                 }
        return None
    except Exception as e:
        logger.error(f"Ошибка при поиске платежа: {e}")
        return None


def create_webhook_app():
    """
    Создание приложения для обработки webhook'ов
    """
    app = web.Application()
    app.router.add_post('/cryptobot-webhook', handle_cryptobot_webhook)
    return app
