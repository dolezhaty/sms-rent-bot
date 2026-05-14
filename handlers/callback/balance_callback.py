"""
Обработчик пополнения баланса
"""

from aiogram import types
from aiogram.dispatcher import FSMContext
from loader import dp, bot
from bin.states import BotStates
from bin.payments.cryptobot.cryptobot import cryptobot
from bin.payments.xrocket.xrocket import xrocket
from bin.banners import create_profile_keyboard
import database
import logging

logger = logging.getLogger(__name__)

# 1. Нажатие кнопки "Пополнить баланс"
@dp.callback_query_handler(lambda c: c.data == "add_balance", state="*")
async def add_balance_start(call: types.CallbackQuery, state: FSMContext):
    await BotStates.add_balance.set()
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Отмена", callback_data="profile"))
    
    text = (
        "<tg-emoji emoji-id=\"5902056028513505203\">💵</tg-emoji> <b>Введите сумму пополнения в USDT:</b>\n\n"
        "<b>Минимальная сумма: $0.5</b>"
    )
    
    try:
        await call.message.edit_caption(
            caption=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception:
        # Если это текстовое сообщение (без картинки), edit_caption упадет
        await call.message.edit_text(
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

@dp.callback_query_handler(lambda c: c.data.startswith("check_topup_xr="))
async def check_topup_xr_callback(call: types.CallbackQuery):
    """
    Проверка пополнения через xRocket
    """
    _, data = call.data.split("=")
    invoice_id, amount_usd_str = data.split("|")
    amount_usd = float(amount_usd_str)
    
    # 1. Проверяем в БД, не оплачен ли уже этот инвойс
    if await database.check_topup_exists(invoice_id):
        await call.answer("✅ Уже зачислено!", show_alert=True)
        try:
             await call.message.edit_reply_markup(reply_markup=create_profile_keyboard())
        except:
             pass
        return

    try:
        user_id = call.from_user.id
        invoice_data = await xrocket.get_invoice(invoice_id)
        # У xRocket статус в invoice_data['status'], оплаченное состояние - 'paid'
        status = invoice_data.get('status')
        
        if status == 'paid':
            amount_final = amount_usd
            
            if await database.add_topup(user_id, invoice_id, amount_usd, amount_final):
                # Если записалось успешно - значит это ПЕРВЫЙ раз
                await database.update_user_balance(user_id, amount_final)
                
                # Добавляем в логи
                user_data_log = await database.get_user(user_id)
                username_log = user_data_log.username if user_data_log and user_data_log.username else "no_username"
                await database.add_action_log(
                    user_id=user_id,
                    username=username_log,
                    action_type="topup",
                    details=f"Пополнение баланса на ${amount_final} через xRocket (Manual check, Invoice: {invoice_id})"
                )
                
                # --- Реферальная система ---
                user_data = await database.get_user(user_id)
                if user_data and user_data.inviting and user_data.inviting != 0:
                    referrer_id = user_data.inviting
                    bonus_amount = round(amount_final * 0.1, 2)
                    if bonus_amount > 0:
                        await database.update_user_balance(referrer_id, bonus_amount)
                        await database.add_referral_history(referrer_id, user_id, amount_final, bonus_amount)
                        
                        # Уведомляем реферера
                        referral_name = f"ID: {user_id}"
                        if user_data.username:
                            referral_name = f"@{user_data.username}"
                            
                        ref_text = (
                            f"<tg-emoji emoji-id='5902335789798265487'>👤</tg-emoji> <b>Ваш реферал {referral_name} пополнил счет!</b>\n"
                            f"<tg-emoji emoji-id='6041705726206808304'>💰</tg-emoji> <b>Вам начислено 10% бонуса: ${bonus_amount}</b>"
                        )
                        try:
                            await bot.send_message(referrer_id, ref_text, parse_mode="HTML")
                        except Exception as e:
                            logger.error(f"Error sending referral notification: {e}")
                # ---------------------------
                
                new_balance = await database.get_user_balance(user_id)
                
                logger.info(f"User {user_id} topped up ${amount_final} via xRocket (Invoice {invoice_id})")
                
                text = (
                    f"✅ <b>Баланс успешно пополнен на ${amount_final}!</b>\n"
                    f"💰 <b>Текущий баланс: ${round(new_balance, 2)}</b>"
                )
                
                try:
                    await call.message.edit_text(
                        text=text,
                        parse_mode="HTML",
                        reply_markup=create_profile_keyboard()
                    )
                except Exception:
                    await call.message.answer(text, parse_mode="HTML", reply_markup=create_profile_keyboard())
            else:
                 await call.answer("✅ Уже зачислено!", show_alert=True)
                 
        elif status == 'active':
            await call.answer("⏳ Оплата еще не поступила. Попробуйте позже.", show_alert=True)
        elif status == 'expired':
            await call.answer("❌ Время оплаты истекло.", show_alert=True)
        else:
            await call.answer(f"Статус платежа: {status}", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error checking xRocket topup: {e}")
        await call.answer("Ошибка проверки платежа", show_alert=True)

# 3. Проверка оплаты
@dp.callback_query_handler(lambda c: c.data.startswith("check_topup="))
async def check_topup_callback(call: types.CallbackQuery):
    # Throttling manual check (хотя глобальный throttling лучше)
    # Но здесь важнее проверка в БД
    
    _, data = call.data.split("=")
    invoice_id, amount_usd_str = data.split("|")
    amount_usd = float(amount_usd_str)
    
    # 1. Проверяем в БД, не оплачен ли уже этот инвойс
    if await database.check_topup_exists(invoice_id):
        await call.answer("✅ Уже зачислено!", show_alert=True)
        # Можно обновить сообщение, убрав кнопку проверки
        try:
             await call.message.edit_reply_markup(reply_markup=create_profile_keyboard())
        except:
             pass
        return

    try:
        status = await cryptobot.check_invoice_status(invoice_id)
        
        if status == 'paid':
            # Зачисляем баланс 1:1 в USD
            amount_final = amount_usd
            user_id = call.from_user.id
            
            # 2. Пытаемся записать в БД
            if await database.add_topup(user_id, invoice_id, amount_usd, amount_final):
                # Если записалось успешно - значит это ПЕРВЫЙ раз
                await database.update_user_balance(user_id, amount_final)
                
                # Добавляем в логи
                user_data_log = await database.get_user(user_id)
                username_log = user_data_log.username if user_data_log and user_data_log.username else "no_username"
                await database.add_action_log(
                    user_id=user_id,
                    username=username_log,
                    action_type="topup",
                    details=f"Пополнение баланса на ${amount_final} через CryptoBot (Manual check, Invoice: {invoice_id})"
                )
                
                # --- Реферальная система ---
                user_data = await database.get_user(user_id)
                if user_data and user_data.inviting and user_data.inviting != 0:
                    referrer_id = user_data.inviting
                    bonus_amount = round(amount_final * 0.1, 2)
                    if bonus_amount > 0:
                        await database.update_user_balance(referrer_id, bonus_amount)
                        await database.add_referral_history(referrer_id, user_id, amount_final, bonus_amount)
                        
                        # Уведомляем реферера
                        referral_name = f"ID: {user_id}"
                        if user_data.username:
                            referral_name = f"@{user_data.username}"
                        
                        ref_text = (
                            f"<tg-emoji emoji-id='5902335789798265487'>👤</tg-emoji> <b>Ваш реферал {referral_name} пополнил счет!</b>\n"
                            f"<tg-emoji emoji-id='6041705726206808304'>💰</tg-emoji> <b>Вам начислено 10% бонуса: ${bonus_amount}</b>"
                        )
                        try:
                            await bot.send_message(referrer_id, ref_text, parse_mode="HTML")
                        except Exception as e:
                            logger.error(f"Error sending referral notification: {e}")
                # ---------------------------
                
                new_balance = await database.get_user_balance(user_id)
                
                logger.info(f"User {user_id} topped up ${amount_final} via CryptoBot (Invoice {invoice_id})")
                
                text = (
                    f"✅ <b>Баланс успешно пополнен на ${amount_final}!</b>\n"
                    f"💰 <b>Текущий баланс: ${round(new_balance, 2)}</b>"
                )
                
                try:
                    await call.message.edit_text(
                        text=text,
                        parse_mode="HTML",
                        reply_markup=create_profile_keyboard()
                    )
                except Exception:
                    await call.message.answer(text, parse_mode="HTML", reply_markup=create_profile_keyboard())
            else:
                 # Если не записалось (IntegrityError), значит уже было
                 await call.answer("✅ Уже зачислено!", show_alert=True)
                 
        elif status == 'active':
            await call.answer("⏳ Оплата еще не поступила. Попробуйте позже.", show_alert=True)
        else:
            await call.answer(f"Статус платежа: {status}", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error checking topup: {e}")
        await call.answer("Ошибка проверки платежа", show_alert=True)
