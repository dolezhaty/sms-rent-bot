"""
Обработчики для платежей через CryptoBot
"""

from aiogram import types
from aiogram.dispatcher import FSMContext

import database
from loader import dp
from bin.payments.cryptobot.cryptobot import cryptobot
from bin.keyboards import CLOSE_BTN
from bin.strings import get_cheque_num


# Обработчик payment=cryptobot перенесен в bin/purchase/purchase.py

# Тестовый обработчик удален - используется основной ниже

@dp.callback_query_handler(lambda c: c.data == "cancel_payment")
async def cancel_payment_callback(call: types.CallbackQuery, state: FSMContext):
    """
    Обработчик отмены платежа
    """
    await call.message.delete()
    await state.finish()
    await call.message.answer("Платеж отменен")


# Старый обработчик удален


async def process_successful_payment(call: types.CallbackQuery, state: FSMContext, purchase_data):
    """
    Обработка успешной оплаты
    """
    try:
        print(f"Обрабатываем успешную оплату: {purchase_data}")  # Отладочная информация
        
        # Генерируем чек
        cheque = get_cheque_num()
        purchase_data['cheque'] = cheque
        
        # Записываем покупку в БД
        sale_id = await database.add_buy(purchase_data)
        print(f"Покупка записана в БД с ID: {sale_id}")  # Отладочная информация
        
        # Получаем данные товара
        item_data = await database.get_item_data(purchase_data['item_id'], purchase_data['count'], True)
        print(f"Получены данные товара: {len(item_data) if item_data else 0} записей")  # Отладочная информация
        
        # Записываем данные проданного товара
        await database.add_sold_item_data(sale_id, item_data)
        
        # Формируем сообщение с данными товара
        item_info = ""
        for item in item_data:
            data = item.data if hasattr(item, 'data') else item[2]
            item_info += f"📱 {data}\n\n"
        
        success_message = f"✅ Оплата прошла успешно!\n\n" \
                         f"🆔 Чек: {cheque}\n" \
                         f"📦 Товар: {purchase_data['item_name']}\n" \
                         f"💰 Сумма: {purchase_data['amount']} руб.\n\n" \
                         f"📱 Данные товара:\n\n" \
                         f"{item_info}" \
                         f"🎉 Спасибо за покупку!"
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main"))
        
        await call.message.answer(success_message, reply_markup=keyboard)
        
        # Завершаем состояние
        await state.finish()
        
    except Exception as e:
        await call.message.answer(f"❌ Ошибка при обработке покупки: {str(e)}")


@dp.callback_query_handler(lambda c: c.data == "check_xrocket_payment", state="*")
async def check_xrocket_payment_callback(call: types.CallbackQuery, state: FSMContext):
    """
    Обработчик проверки оплаты через xRocket
    """
    try:
        await call.answer("🔄 Проверяем оплату...")
        
        # Получаем данные о платеже из БД
        last_payment = await database.get_last_payment(call.from_user.id)
        
        if not last_payment:
            await call.message.answer("❌ Ошибка: данные об инвойсе не найдены. Попробуйте создать новый платеж.")
            return

        invoice_id = last_payment.get('invoice_id')
        purchase_data = last_payment.get('purchase_data')

        if not invoice_id or not purchase_data:
            await call.message.answer("❌ Ошибка: данные об инвойсе не найдены. Попробуйте создать новый платеж.")
            return

        # Проверяем статус инвойса
        from bin.payments.xrocket.xrocket import xrocket
        
        try:
            invoice_data = await xrocket.get_invoice(invoice_id)
            status = invoice_data.get('status')
        except Exception as api_error:
            await call.message.answer(f"❌ Ошибка при обращении к xRocket: {str(api_error)}")
            return

        if status == "paid":
            # Оплата прошла успешно
            await process_successful_payment_callback(call, purchase_data)
            # Завершаем состояние после успешной обработки
            await state.finish()
        elif status == "expired":
            await call.message.answer("❌ Время оплаты истекло. Попробуйте создать новый платеж.")
        elif status == "active":
            await call.message.answer("⏳ Оплата еще не поступила. Попробуйте еще раз через несколько секунд.")
        else:
            await call.message.answer(f"❓ Статус платежа: {status}")
        
    except Exception as e:
        logger.error(f"Error checking xRocket payment: {e}")
        await call.message.answer(f"❌ Ошибка при проверке платежа: {str(e)}")
        await state.finish()

# Обработчики для CryptoBot платежей
@dp.callback_query_handler(lambda c: c.data == "check_cryptobot_payment", state="*")
async def check_cryptobot_payment_callback(call: types.CallbackQuery, state: FSMContext):
    """
    Обработчик проверки оплаты через CryptoBot
    """
    print("PAYMENT: Обработчик check_cryptobot_payment сработал!")
    
    try:
        await call.answer("🔄 Проверяем оплату...")
        print("PAYMENT: Получаем данные о платеже из БД...")
        # Получаем данные о платеже из БД
        last_payment = await database.get_last_payment(call.from_user.id)
        print(f"PAYMENT: Данные из БД: {last_payment}")
        
        if not last_payment:
            print("PAYMENT: Данные об инвойсе не найдены в БД")
            await call.message.answer("❌ Ошибка: данные об инвойсе не найдены. Попробуйте создать новый платеж.")
            return

        invoice_id = last_payment.get('invoice_id')
        purchase_data = last_payment.get('purchase_data')

        if not invoice_id or not purchase_data:
            print("PAYMENT: Неполные данные об инвойсе")
            await call.message.answer("❌ Ошибка: данные об инвойсе не найдены. Попробуйте создать новый платеж.")
            return

        print(f"PAYMENT: Invoice ID: {invoice_id}, Purchase data: {purchase_data}")
        
        # Проверяем статус инвойса
        from bin.payments.cryptobot.cryptobot import cryptobot
        print(f"PAYMENT: Проверяем статус инвойса {invoice_id} в CryptoBot...")
        
        try:
            status = await cryptobot.check_invoice_status(invoice_id)
            print(f"PAYMENT: Статус инвойса получен: {status}")
        except Exception as api_error:
            print(f"PAYMENT: Ошибка при обращении к CryptoBot API: {api_error}")
            await call.message.answer(f"❌ Ошибка при обращении к CryptoBot: {str(api_error)}")
            return

        if status == "paid":
            print("PAYMENT: Оплата подтверждена, обрабатываем покупку...")
            # Оплата прошла успешно
            await process_successful_payment_callback(call, purchase_data)
            # Завершаем состояние после успешной обработки
            await state.finish()
        elif status == "expired":
            print("PAYMENT: Время оплаты истекло")
            await call.message.answer("❌ Время оплаты истекло. Попробуйте создать новый платеж.")
        elif status == "active":
            print("PAYMENT: Оплата еще не поступила")
            await call.message.answer("⏳ Оплата еще не поступила. Попробуйте еще раз через несколько секунд.")
        elif status is None:
            print("PAYMENT: Не удалось получить статус")
            await call.message.answer("❌ Не удалось получить статус платежа. Попробуйте позже.")
        else:
            print(f"PAYMENT: Неизвестный статус: {status}")
            await call.message.answer(f"❓ Неизвестный статус платежа: {status}")
        
        # Завершаем обработку callback'а
        await call.answer()

    except Exception as e:
        print(f"PAYMENT: Критическая ошибка при проверке оплаты: {str(e)}")
        import traceback
        traceback.print_exc()
        await call.message.answer(f"❌ Ошибка при проверке платежа: {str(e)}")
        await call.answer()
        await state.finish()


async def process_successful_payment_callback(call: types.CallbackQuery, purchase_data):
    """
    Обработка успешной оплаты через CryptoBot
    """
    try:
        print(f"Обрабатываем успешную оплату: {purchase_data}")
        
        # Генерируем чек
        cheque = get_cheque_num()
        purchase_data['cheque'] = cheque
        
        # Записываем покупку в БД
        sale_id = await database.add_buy(purchase_data)
        print(f"Покупка записана в БД с ID: {sale_id}")
        
        # Получаем данные товара
        item_data = await database.get_item_data(purchase_data['item_id'], purchase_data['count'], True)
        print(f"Получены данные товара: {len(item_data) if item_data else 0} записей")
        
        # Записываем данные проданного товара
        await database.add_sold_item_data(sale_id, item_data)
        
        # Отправляем сообщение об успешной оплате в новом формате
        from datetime import datetime
        now = datetime.now()
        date_time = now.strftime("%d.%m.%Y %H:%M:%S")
        
        # Формируем сообщение точно как на скриншоте с жирным шрифтом и разделителями
        success_message = f"✅ *Успешная покупка товара*\n\n" \
                         f"━━━━━━━━━━━\n" \
                         f"📦 *Товар:* `{purchase_data['item_name']}` | {purchase_data['count']} шт |\n" \
                         f"━━━━━━━━━━━\n" \
                         f"💰 *${purchase_data['amount']}*\n" \
                         f"━━━━━━━━━━━\n" \
                         f"📄 *Чек:* `{cheque}`\n\n" \
                         f"📅 *Дата:* `{date_time}`"
        
        await call.message.answer(success_message, parse_mode="Markdown")
        
        # Отправляем файлы с данными товара
        for item in item_data:
            file_data = item.data if hasattr(item, 'data') else item[2]  # Данные файла (может быть "file=path" или "text=content")
            try:
                import os
                
                if file_data.startswith('file='):
                    # Это файл - убираем префикс "file="
                    file_path = file_data[5:]  # Убираем "file="
                    print(f"PAYMENT: Отправляем файл: {file_path}")
                    
                    if os.path.exists(file_path):
                        # Определяем тип файла по расширению
                        if file_path.endswith('.txt'):
                            with open(file_path, 'rb') as file:
                                await call.message.answer_document(file, caption=f"📄 {os.path.basename(file_path)}")
                        elif file_path.endswith(('.jpg', '.jpeg', '.png')):
                            with open(file_path, 'rb') as file:
                                await call.message.answer_photo(file, caption=f"🖼️ {os.path.basename(file_path)}")
                        elif file_path.endswith('.mp4'):
                            with open(file_path, 'rb') as file:
                                await call.message.answer_video(file, caption=f"🎥 {os.path.basename(file_path)}")
                        else:
                            # Для других типов файлов отправляем как документ
                            with open(file_path, 'rb') as file:
                                await call.message.answer_document(file, caption=f"📎 {os.path.basename(file_path)}")
                    else:
                        print(f"PAYMENT: Файл не найден: {file_path}")
                        await call.message.answer(f"❌ Файл не найден: {file_path}")
                        
                elif file_data.startswith('text='):
                    # Это текст - отправляем как сообщение
                    text_content = file_data[5:]  # Убираем "text="
                    print(f"PAYMENT: Отправляем текст: {text_content}")
                    await call.message.answer(f"📝 {text_content}")
                else:
                    # Неизвестный формат
                    print(f"PAYMENT: Неизвестный формат данных: {file_data}")
                    await call.message.answer(f"❓ Неизвестный формат данных: {file_data}")
                    
            except Exception as file_error:
                print(f"PAYMENT: Ошибка при отправке файла {file_data}: {file_error}")
                await call.message.answer(f"❌ Ошибка при отправке файла: {str(file_error)}")
        
        # Отправляем финальное сообщение с кнопкой главного меню
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main"))
        await call.message.answer("🎉 Спасибо за покупку!", reply_markup=keyboard)
        
        print("PAYMENT: Покупка успешно обработана!")
        
    except Exception as e:
        print(f"Ошибка при обработке покупки: {str(e)}")
        await call.message.answer(f"❌ Ошибка при обработке покупки: {str(e)}")
