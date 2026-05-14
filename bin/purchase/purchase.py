import json

from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Regexp
from aiogram.dispatcher.filters.state import StatesGroup, State

import database
from bin.keyboards import get_payment_keyboard, get_keyboard_for_finish
# Удален импорт старых платежей - используется только CryptoBot
from bin.purchase.register_purchase import register_purchase
from loader import dp
from src.const import const_ru
from bin.strings import create_comment, get_pay_message, get_now_date


class PurchaseCreator(StatesGroup):
    item_count = State()
    select_pay = State()
    check_purchase = State()


async def select_count(message: types.Message, item_id):
    """
    Клавиатура для выбора количества товаров

    :param message:
    :param item_id: id выброанного товара
    :return:
    """
    await PurchaseCreator.item_count.set()

    item_count = await database.get_item_count(item_id)

    state = Dispatcher.get_current().current_state()
    await state.update_data(item_id=item_id)

    keyboard = types.InlineKeyboardMarkup(row_width=5)

    i = 1
    btn_list = []
    while i <= 15 and i <= item_count:
        btn_list.append(types.InlineKeyboardButton(text=f"{str(i)} шт.",
                                                   callback_data=f"select_count={str(i)}"))
        i += 1

    await state.update_data(max_count=item_count)

    keyboard.add(*btn_list)
    keyboard.add(types.InlineKeyboardButton(text="🛒 Своё значение", callback_data="user_count"))
    keyboard.add(types.InlineKeyboardButton(text=const_ru['cancel_buy'], callback_data="cancel_buy"))

    await message.answer("🛒 Введите необходимое количество товара", reply_markup=keyboard)


@dp.callback_query_handler(Regexp("select_count"), state=PurchaseCreator.item_count)
async def get_count_keyboard(call: types.CallbackQuery, state: FSMContext):
    """
    Количество товара из клавиатуры

    :param call:
    :param state:
    :return:
    """
    await call.message.delete()

    await state.update_data(count=int(call.data.split("=")[1]))
    await process_buy_from_balance(call.message, state)


@dp.callback_query_handler(Regexp("user_count"), state=PurchaseCreator.item_count)
async def input_count(call: types.CallbackQuery, state: FSMContext):
    """
    Выбор количества товара для покупки

    :param call:
    :param state:
    :return:
    """
    await call.message.delete()
    data = await state.get_data()
    item_id = data['item_id']

    item_count = await database.get_item_count(item_id)

    await call.message.answer("🛒 Введите количество необходимого товара:\n\n"
                              "Минимальное значение: <i>1 шт.</i>\n"
                              f"Максимальное: <i>{item_count} шт.</i>")

    await state.update_data(max_count=int(item_count))


@dp.message_handler(state=PurchaseCreator.item_count)
async def check_count(message: types.Message, state: FSMContext):
    """
    Проверка количества товара

    :param message:
    :param state:
    :return:
    """
    data = await state.get_data()

    max_count = data['max_count']
    count = message.text

    if count.isdigit() and int(count) <= max_count and int(count) > 0:
        count = int(count)
    else:
        await message.answer(f"❗️ Некорректное значение. Введите число от 1 до {max_count}")
        return

    await state.update_data(count=count)
    await process_buy_from_balance(message, state)


async def process_buy_from_balance(message: types.Message, state: FSMContext):
    """
    Обработка покупки с баланса (без выбора платежной системы)
    """
    data = await state.get_data()
    user_id = message.chat.id
    
    item_data = await database.get_item(data['item_id'])
    count = int(data['count'])
    total_price = float(item_data.price) * count
    
    user_balance = await database.get_user_balance(user_id)
    
    if user_balance < total_price:
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="profile"))
        keyboard.add(types.InlineKeyboardButton(text="Отмена", callback_data="cancel_buy"))
        
        await message.answer(
            f"❌ Недостаточно средств на балансе!\n\n"
            f"💰 Стоимость: <b>${total_price}</b>\n"
            f"💵 Ваш баланс: <b>${user_balance}</b>\n\n"
            f"Пожалуйста, пополните баланс в профиле.",
            reply_markup=keyboard
        )
        await state.finish()
        return

    # Если баланса достаточно, подтверждаем покупку
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="✅ Подтвердить покупку", callback_data="confirm_balance_buy"))
    keyboard.add(types.InlineKeyboardButton(text="Отмена", callback_data="cancel_buy"))
    
    await message.answer(
        f"🛒 <b>Подтверждение покупки</b>\n"
        f"━━━━━━━━━━━\n"
        f"📦 Товар: <b>{item_data.name}</b>\n"
        f"🔢 Количество: <b>{count} шт.</b>\n"
        f"💰 К оплате: <b>${total_price}</b>\n"
        f"━━━━━━━━━━━\n"
        f"Вы уверены, что хотите совершить покупку?",
        reply_markup=keyboard
    )
    await PurchaseCreator.check_purchase.set()


@dp.callback_query_handler(lambda c: c.data == "confirm_balance_buy", state=PurchaseCreator.check_purchase)
async def confirm_balance_buy(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = call.message.chat.id
    
    item_data = await database.get_item(data['item_id'])
    count = int(data['count'])
    total_price = float(item_data.price) * count
    
    # Еще раз проверяем баланс перед списанием
    user_balance = await database.get_user_balance(user_id)
    if user_balance < total_price:
        await call.answer("❌ Недостаточно средств!", show_alert=True)
        await state.finish()
        return
        
    # Списываем баланс
    await database.update_user_balance(user_id, -total_price)
    
    # Регистрируем покупку
    purchase_data = {
        'item_id': data['item_id'],
        'amount': total_price,
        'count': count,
        'payment': 'balance'
    }
    
    await register_purchase(call.message, purchase_data)
    await state.finish()


async def create_purchase(message: types.Message, state: FSMContext):
    """
    Метод оставлен для совместимости, но теперь перенаправляет на оплату с баланса
    """
    await process_buy_from_balance(message, state)


async def select_pay(message: types.Message, state: FSMContext):
    """
    Метод оставлен для совместимости, но теперь перенаправляет на оплату с баланса
    """
    await process_buy_from_balance(message, state)


async def create_cryptobot_purchase(message: types.Message, state: FSMContext):
    """
    Создание покупки через CryptoBot
    
    :param message:
    :param state:
    :return:
    """
    import database
    
    data = await state.get_data()
    
    item_data = await database.get_item(data['item_id'])
    amount = item_data.price * int(data['count'])
    
    # Сохраняем данные о покупке в состоянии
    purchase_data = {
        'user_id': message.chat.id,
        'item_id': data['item_id'],
        'item_name': item_data.name,
        'count': int(data['count']),
        'amount': amount,
        'date': get_now_date()
    }
    
    await state.update_data(purchase_data=purchase_data)
    
    try:
        # Создаем инвойс в CryptoBot
        from bin.payments.cryptobot.cryptobot import cryptobot
        
        # Конвертируем рубли в USDT
        # usdt_amount = await cryptobot.convert_rub_to_usdt(amount)
        # ТЕПЕРЬ СУММА УЖЕ В USD (из БД)
        amount_usd = float(amount)
        
        description = f"Покупка: {item_data.name}"
        invoice = await cryptobot.create_invoice(
            amount=amount_usd,
            currency="USDT",
            description=description
        )
        
        # Сохраняем данные инвойса в состоянии
        await state.update_data(invoice_id=invoice['invoice_id'])
        await state.update_data(invoice_url=invoice['bot_invoice_url'])
        
        # Сохраняем данные платежа в БД
        await database.save_payment_data(
            user_id=message.chat.id,
            invoice_id=invoice['invoice_id'],
            item_id=data['item_id'],
            item_name=item_data.name,
            count=int(data['count']),
            amount=amount_usd,
            date=get_now_date()
        )
        
        # Создаем сообщение с инструкциями
        message_text = f"💳 Оплата через CryptoBot\n\n" \
                      f"📦 Товар: {item_data.name}\n" \
                      f"💰 Сумма: ${amount_usd} (USDT)\n\n" \
                      f"🔗 Ссылка для оплаты:\n" \
                      f"{invoice['bot_invoice_url']}\n\n" \
                      f"📋 Инструкция:\n" \
                      f"1. Нажмите на ссылку выше\n" \
                      f"2. Выберите криптовалюту\n" \
                      f"3. Отправьте указанную сумму\n" \
                      f"4. Вернитесь в бот и нажмите 'Проверить оплату'\n\n" \
                      f"⏰ Время на оплату: 15 минут"
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.row(
            types.InlineKeyboardButton("🔗 Открыть ссылку", url=invoice['bot_invoice_url']),
            types.InlineKeyboardButton("✅ Проверить оплату", callback_data="check_cryptobot_payment")
        )
        keyboard.add(types.InlineKeyboardButton("Отменить", callback_data="cancel_payment"))
        
        await message.answer(message_text, reply_markup=keyboard)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при создании платежа: {str(e)}")


async def create_purchase(message: types.Message, state: FSMContext):
    """
    Обработка покупки (CryptoBot + xRocket)
    """
    await create_multi_payment_purchase(message, state)


@dp.callback_query_handler(Regexp("check_buy"), state=PurchaseCreator.check_purchase)
async def check_purchase(call: types.CallbackQuery, state: FSMContext):
    """
    Проверка покупки

    :param call:
    :param state:
    :return:
    """
    data = await state.get_data()
    await register_purchase(call.message, data)


@dp.callback_query_handler(Regexp("cancel_buy"), state=PurchaseCreator)
async def cancel_buy(call: types.CallbackQuery):
    """
    Отмена покупки

    :param call:
    :return:
    """
    await call.message.delete()
    await call.message.answer("❗️ Покупка отменена")

    state = Dispatcher.get_current().current_state()
    await state.finish()
