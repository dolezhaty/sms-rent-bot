import asyncio
import logging
import time
from bin.api_5sim import FiveSimAPI
from loader import bot
import database
from aiogram import types
from bin.strings import get_now_date
from bin.country_utils import get_country_info
from src.config import CRYPTOBOT_COMMISSION
from bin.pricing import calculate_dynamic_markup
import math

logger = logging.getLogger(__name__)

async def start_checker():
    logger.info("SMS Checker started")
    while True:
        try:
            await check_orders()
        except Exception as e:
            logger.error(f"Error in SMS checker: {e}")
        
        await asyncio.sleep(5)

async def check_orders():
    # Получаем активные заказы из БД
    orders = await database.get_active_orders()
    
    if not orders:
        return

    for order in orders:
        try:
            # 0. Проверяем статус в БД (вдруг он изменился параллельно)
            # В get_active_orders мы берем только PENDING, но пока мы шли по циклу,
            # кто-то мог его отменить.
            # Лучше перепроверить перед действием, если это критично.
            # Но get_active_orders возвращает объекты. Если мы работаем быстро, то норм.
            
            # 1. Проверяем срок действия (15 минут)
            now = time.time()
            if now > order.expires_at:
                # Еще раз проверяем актуальный статус в БД, чтобы не отменить уже отмененный вручную
                fresh_order = await database.get_order(order.order_id)
                if fresh_order and fresh_order.status != 'PENDING':
                    continue
                    
                await process_expired_order(order)
                continue
                
            # 2. Проверяем статус в 5sim
            info = await FiveSimAPI.check_order(order.order_id)
            if not info:
                continue
                
            status = info.get('status')
            sms_list = info.get('sms', [])
            
            if sms_list:
                # СМС пришло!
                await process_success_order(order, info, sms_list[0])
            elif status == 'FINISHED' or status == 'BANNED':
                # Заказ завершен без СМС? Или мы пропустили?
                # Если FINISHED но смс нет в списке, возможно что-то не так.
                # Но если sms_list пуст, а статус FINISHED, значит он завершен.
                # Обычно FINISHED ставится после получения смс и нажатия finish.
                # Если 5sim сам закрыл, то скорее всего CANCELED или TIMEOUT (в 5sim статус CANCELED или EXPIRED?)
                # У 5sim статусы: PENDING, RECEIVED (смс пришло?), CANCELED, TIMEOUT, FINISHED, BANNED
                # Если RECEIVED - смс есть.
                pass
            elif status == 'CANCELED' or status == 'TIMEOUT':
                 # Заказ отменен на стороне 5sim
                 await process_cancelled_external(order)
                 
        except Exception as e:
            logger.error(f"Error checking order {order.order_id}: {e}")

async def process_success_order(order, info, sms):
    logger.info(f"Order {order.order_id} success! SMS received.")
    
    # 1. Записываем в логи
    user_id = order.user_id
    order_id = order.order_id
    code = sms.get('code')
    user_data_log = await database.get_user(user_id)
    username_log = user_data_log.username if user_data_log and user_data_log.username else "no_username"
    await database.add_action_log(
        user_id=user_id,
        username=username_log,
        action_type="sms_received",
        details=f"Получено СМС для {order.phone}: {code} (ID заказа: {order_id})"
    )

    # 2. Обновляем статус в БД (атомарно) - если уже обработан, пропускаем
    try:
        updated = await database.update_order_status(order.order_id, 'FINISHED')
    except Exception as e:
        logger.error(f'Failed to update order status atomically: {e}')
        updated = False

    if not updated:
        logger.warning(f'Order {order.order_id} already processed or update failed; skipping')
        return
    
    # 2. Записываем в историю покупок (если еще нет)
    # Используем логику из order_callback
    from src.database_models import Sale
    from sqlalchemy import select
    from database import async_session
    
    is_recorded = False
    async with async_session() as session:
         res = await session.execute(select(Sale).where(Sale.cheque == str(order.order_id)))
         if res.scalar_one_or_none():
             is_recorded = True
    
    if not is_recorded:
        # Расчет стоимости (как в order_callback)
        # Берем цену из info (реальная себестоимость)
        real_price = float(info.get('price', 0))
        price_with_margin = calculate_dynamic_markup(real_price)
        final_cost_usd = price_with_margin / (1 - CRYPTOBOT_COMMISSION)
        final_cost_usd = math.ceil(final_cost_usd * 100) / 100
        
        c_code = info.get('country')
        s_name = info.get('product')
        c_info = get_country_info(c_code)
        country_name = c_info['name'] if c_info else c_code.title()
        
        purchase_data = {
            'user_id': order.user_id,
            'item_name': f"{s_name.capitalize()} ({country_name})",
            'amount': final_cost_usd,
            'count': 1,
            'date': get_now_date(),
            'cheque': str(order.order_id)
        }
        # add_buy_safe returns inserted id or False if exists
        added = await database.add_buy_safe(purchase_data)
        if not added:
            logger.warning(f'Sale for cheque {purchase_data["cheque"]} already exists, skipping')
    
    # 3. Отправляем уведомление пользователю (редактируем сообщение заказа)
    code = sms.get('code')
    text = sms.get('text')
    
    # Форматирование
    e_sms_success = '<tg-emoji emoji-id="5895713431264170680">✅</tg-emoji>'
    e_phone = '<tg-emoji emoji-id="5258337316715373336">📱</tg-emoji>'
    e_code = '<tg-emoji emoji-id="5429571366384842791">🔢</tg-emoji>'
    e_text = '<tg-emoji emoji-id="5257965174979042426">📩</tg-emoji>'
    
    text_formatted = text
    if code and code in text_formatted:
        text_formatted = text_formatted.replace(code, f"<code>{code}</code>")

    msg_text = f"{e_sms_success} <b>СМС ПРИШЛО!</b>\n" \
               f"<b>━━━━━━━━━━━</b>\n" \
               f"{e_phone} <b>Номер: <code>{order.phone}</code></b>\n" \
               f"{e_code} <b>Код: <code>{code}</code></b>\n" \
               f"<b>━━━━━━━━━━━</b>\n" \
               f"{e_text} <b>Текст: {text_formatted}</b>\n\n" \
               f"<i>Заказ автоматически завершен.</i>"
    
    # Убираем кнопки (Завершить больше не нужно)
    keyboard = None 
    
    try:
        # Пытаемся редактировать сообщение, если знаем message_id
        if order.message_id and order.chat_id:
            try:
                # ЗАКРЕПЛЯЕМ СООБЩЕНИЕ С КОДОМ
                await bot.pin_chat_message(chat_id=order.chat_id, message_id=order.message_id)
            except:
                pass
                
            try:
                await bot.edit_message_caption(chat_id=order.chat_id, message_id=order.message_id, caption=msg_text, reply_markup=keyboard, parse_mode="HTML")
            except:
                await bot.edit_message_text(chat_id=order.chat_id, message_id=order.message_id, text=msg_text, reply_markup=keyboard, parse_mode="HTML")
        else:
            # Если не знаем ID, просто шлем новое
            sent_msg = await bot.send_message(order.user_id, msg_text, parse_mode="HTML")
            try:
                await bot.pin_chat_message(chat_id=order.user_id, message_id=sent_msg.message_id)
            except:
                pass
    except Exception as e:
        logger.error(f"Failed to notify user about success: {e}")
        
    # 4. Завершаем заказ в 5sim
    await FiveSimAPI.finish_order(order.order_id)


async def process_expired_order(order):
    # ПРОВЕРКА ПЕРЕД ОТМЕНОЙ (Double Check)
    # Проверяем статус в БД еще раз
    fresh_order = await database.get_order(order.order_id)
    if not fresh_order or fresh_order.status != 'PENDING':
        logger.info(f"Order {order.order_id} was already processed (status: {fresh_order.status if fresh_order else 'None'}). Skipping expiration.")
        return

    logger.info(f"Order {order.order_id} expired. Cancelling...")
    
    # 1. Отменяем в 5sim
    cancel_result = await FiveSimAPI.cancel_order(order.order_id)
    
    # Если ошибка (например, уже отменен или завершен), проверяем статус
    if not cancel_result or 'error' in cancel_result:
        info = await FiveSimAPI.check_order(order.order_id)
        
        # Если заказ уже отменен (CANCELED), значит мы опоздали или юзер сам отменил
        # Если статус FINISHED/SMS - успех
        if info:
             if info.get('status') == 'FINISHED' or info.get('sms'):
                 if info.get('sms'):
                    await process_success_order(order, info, info['sms'][0])
                 return
             elif info.get('status') == 'CANCELED' or info.get('status') == 'TIMEOUT':
                 # Он уже отменен. 
                 # Проверяем, меняли ли мы статус в БД.
                 # Если в БД он все еще PENDING, значит нужно вернуть деньги (так как юзер не отменял через бота, иначе статус был бы CANCELLED)
                 # НО! Если юзер нажал "Отменить" секунду назад, статус в БД мог стать CANCELLED.
                 # Мы это проверили в начале функции.
                 pass

    # 2. Возврат средств
    # Еще раз проверяем статус в БД перед возвратом (атомарность насколько возможно)
    fresh_order = await database.get_order(order.order_id)
    if fresh_order.status != 'PENDING':
         return

    # Получаем цену продажи (которую списали)
    refund_amount = order.price
    
    # Записываем в логи (автоматическая отмена)
    user_data_log = await database.get_user(order.user_id)
    username_log = user_data_log.username if user_data_log and user_data_log.username else "no_username"
    await database.add_action_log(
        user_id=order.user_id,
        username=username_log,
        action_type="refund",
        details=f"Автоматический возврат за номер {order.phone} на сумму ${refund_amount:.2f} (Истекло время)"
    )

    # Атомарно возвращаем средства
    await database.update_user_balance(order.user_id, refund_amount)
    
    # 3. Обновляем статус
    await database.update_order_status(order.order_id, 'EXPIRED')
    
    # 4. Уведомляем
    
    # Custom Emojis for Expired
    # Cancel: 5260726538302660868
    # Refund: 5258419835922030550
    
    e_cancel = '<tg-emoji emoji-id="5260726538302660868">❌</tg-emoji>'
    e_refund = '<tg-emoji emoji-id="5258419835922030550">💰</tg-emoji>'
    
    msg_text = f"{e_cancel} <b>Заказ отменен автоматически.</b>\n" \
               f"{e_refund} <b>Средства возвращены: <code>${refund_amount:.2f}</code></b>"
               
    try:
        if order.message_id and order.chat_id:
            try:
                # Пытаемся закрепить сообщение с результатом
                await bot.pin_chat_message(chat_id=order.chat_id, message_id=order.message_id)
            except:
                pass
                
            try:
                await bot.edit_message_caption(chat_id=order.chat_id, message_id=order.message_id, caption=msg_text, reply_markup=None, parse_mode="HTML")
            except:
                await bot.edit_message_text(chat_id=order.chat_id, message_id=order.message_id, text=msg_text, reply_markup=None, parse_mode="HTML")
        else:
            sent_msg = await bot.send_message(order.user_id, msg_text, parse_mode="HTML")
            try:
                await bot.pin_chat_message(chat_id=order.user_id, message_id=sent_msg.message_id)
            except:
                pass
    except:
        pass

async def process_cancelled_external(order):
    # ПРОВЕРКА ПЕРЕД ОТМЕНОЙ (Double Check)
    # Проверяем статус в БД еще раз
    fresh_order = await database.get_order(order.order_id)
    if not fresh_order or fresh_order.status != 'PENDING':
        logger.info(f"Order {order.order_id} was already processed externally (status: {fresh_order.status if fresh_order else 'None'}). Skipping.")
        return

    # Если заказ отменен со стороны 5sim (например, нет номеров или таймаут)
    # Делаем возврат
    logger.info(f"Order {order.order_id} cancelled externally.")
    
    refund_amount = order.price
    
    # Записываем в логи (внешняя отмена)
    user_data_log = await database.get_user(order.user_id)
    username_log = user_data_log.username if user_data_log and user_data_log.username else "no_username"
    await database.add_action_log(
        user_id=order.user_id,
        username=username_log,
        action_type="refund",
        details=f"Возврат за номер {order.phone} на сумму ${refund_amount:.2f} (Отмена сервисом)"
    )

    current_balance = await database.get_user_balance(order.user_id)
    await database.set_user_balance(order.user_id, current_balance + refund_amount)
    
    await database.update_order_status(order.order_id, 'CANCELLED')
    
    msg_text = f"<b>❌ Заказ отменен сервисом.</b>\n" \
               f"<b>💰 Средства возвращены: ${refund_amount:.2f}</b>"
    try:
        if order.message_id and order.chat_id:
            try:
                await bot.edit_message_caption(chat_id=order.chat_id, message_id=order.message_id, caption=msg_text, reply_markup=None, parse_mode="HTML")
            except:
                await bot.edit_message_text(chat_id=order.chat_id, message_id=order.message_id, text=msg_text, reply_markup=None, parse_mode="HTML")
    except:
        pass
