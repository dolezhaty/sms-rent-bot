 
"""
Обработчик ввода суммы для пополнения баланса
"""
from aiogram import types
from aiogram.dispatcher import FSMContext
from loader import dp
from bin.states import BotStates
from bin.payments.cryptobot.cryptobot import cryptobot
from bin.payments.xrocket.xrocket import xrocket
import database
from bin.strings import get_now_date
import logging

logger = logging.getLogger(__name__)

@dp.message_handler(state=BotStates.add_balance)
async def process_balance_amount(message: types.Message, state: FSMContext):
    try:
        amount_usd = float(message.text.replace(',', '.'))
        if amount_usd < 0.5:
            await message.answer("❌ Минимальная сумма пополнения - $0.5")
            return
            
        await state.finish()
        
        try:
            # Создаем инвойс CryptoBot
            invoice_crypto = await cryptobot.create_invoice(
                amount=amount_usd,
                currency="USDT",
                description=f"Top up balance: ${amount_usd}",
                payload=str(message.from_user.id)
            )
            
            # Создаем инвойс xRocket
            invoice_rocket = await xrocket.create_invoice(
                amount=amount_usd,
                currency="USDT",
                description=f"Top up balance: ${amount_usd}",
                payload=str(message.from_user.id)
            )
            
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            keyboard.row(types.InlineKeyboardButton("Оплатить (CryptoBot)", url=invoice_crypto['bot_invoice_url']))
            keyboard.row(types.InlineKeyboardButton("Оплатить (xRocket)", url=invoice_rocket['link']))
            keyboard.row(types.InlineKeyboardButton("Назад", callback_data="profile"))
            
            text = (
                f"<tg-emoji emoji-id='5902056028513505203'>💳</tg-emoji> <b>Пополнение баланса</b>\n"
                f"━━━━━━━━━━━\n"
                f"<tg-emoji emoji-id='5258204546391351475'>💰</tg-emoji> <b>Сумма: ${amount_usd} (USDT)</b>\n\n"
                "🔗 <b>Для оплаты перейдите по кнопке ниже.</b>\n"
                "<i>Баланс пополнится автоматически после оплаты.</i>"
            )
            
            sent_message = await message.answer(
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
            # Сохраняем данные о платеже CryptoBot
            await database.save_payment_data(
                user_id=message.from_user.id,
                invoice_id=invoice_crypto['invoice_id'],
                item_id=0, # 0 для пополнения баланса
                item_name="Balance Topup (CryptoBot)",
                count=1,
                amount=amount_usd,
                date=get_now_date(),
                message_id=sent_message.message_id,
                chat_id=sent_message.chat.id
            )
            
            # Сохраняем данные о платеже xRocket
            await database.save_payment_data(
                user_id=message.from_user.id,
                invoice_id=str(invoice_rocket['id']),
                item_id=0, # 0 для пополнения баланса
                item_name="Balance Topup (xRocket)",
                count=1,
                amount=amount_usd,
                date=get_now_date(),
                message_id=sent_message.message_id,
                chat_id=sent_message.chat.id
            )
            
        except Exception as e:
            logger.error(f"Failed to create invoices: {e}")
            await message.answer(f"❌ Ошибка при создании счета: {str(e)}")
        
    except ValueError:
        await message.answer("❌ Введите корректное число.")
