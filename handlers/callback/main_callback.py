"""
Обработчики для главного меню и основных функций
"""

import json
import logging
import os
from aiogram import types
from aiogram.dispatcher import FSMContext

import database
from loader import dp
from bin.banners import get_profile_text, create_profile_keyboard, get_faq_text, create_faq_keyboard
from bin.keyboards import user_keyboard, admin_keyboard
from src.config import is_admin
from src.const import const_ru

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dp.callback_query_handler(lambda c: c.data == "profile", state="*")
async def profile_callback(call: types.CallbackQuery, state: FSMContext):
    """
    Обработчик кнопки Профиль
    """
    await state.finish()
    try:
        await call.message.delete()
    except Exception:
        pass
    
    user_data = await database.get_user(str(call.from_user.id))
    if user_data is None:
        await call.message.answer("***❗️ Пользователь не найден***\n***Пропишите /start для авторизации***", parse_mode="Markdown")
        return

    from bin.banners import BANNER_PROFILE, get_profile_text
    profile_text = await get_profile_text(user_data)
    keyboard = create_profile_keyboard()
    
    try:
        with open(BANNER_PROFILE, 'rb') as photo:
            await call.message.answer_photo(photo, caption=profile_text, reply_markup=keyboard, parse_mode="HTML")
    except FileNotFoundError:
        await call.message.answer(profile_text, reply_markup=keyboard, parse_mode="HTML")


@dp.callback_query_handler(lambda c: c.data == "referral_menu", state="*")
async def referral_menu_callback(call: types.CallbackQuery, state: FSMContext):
    """
    Обработчик кнопки Реферальная система
    """
    await state.finish()
    try:
        await call.message.delete()
    except Exception:
        pass
    
    user_id = call.from_user.id
    count, earnings = await database.get_referral_stats(user_id)
    
    # Генерация ссылки
    bot_info = await call.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=REF{user_id}"
    
    e_ref = '<tg-emoji emoji-id="5188153943326208607">👥</tg-emoji>'
    e_gift = '<tg-emoji emoji-id="5893102202817352158">🤝</tg-emoji>'
    e_link = '<tg-emoji emoji-id="5902056028513505203">🔗</tg-emoji>'
    e_stats = '<tg-emoji emoji-id="5258204546391351475">📊</tg-emoji>'

    text = (
        f"<b>{e_ref} Реферальная система</b>\n\n"
        f"<b>{e_gift} Приглашайте друзей и получайте 10% от их пополнений!</b>\n\n"
        f"<b>{e_link} Ваша ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"<b>{e_stats} Статистика:</b>\n"
        f"<b>└ Приглашено: {count}</b>\n"
        f"<b>└ Заработано: ${round(earnings, 2)}</b>"
    )
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Назад", callback_data="profile"))
    
    try:
        await call.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error sending referral menu: {e}")
        # Самый простой вариант без разметки
        simple_text = f"Реферальная система\n\nСсылка: {ref_link}\nПриглашено: {count}\nЗаработано: ${round(earnings, 2)}"
        await call.message.answer(simple_text, reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == "api_menu", state="*")
async def api_menu_callback(call: types.CallbackQuery, state: FSMContext):
    """
    Обработчик кнопки API для разработчиков
    """
    await state.finish()
    try:
        await call.message.delete()
    except Exception:
        pass

    user_id = call.from_user.id
    user = await database.get_user(user_id)

    if not user.api_key:
        api_key = await database.generate_api_key(user_id)
    else:
        api_key = user.api_key

    docs_url = "https://shopup.sbs/docs"

    e_api  = '<tg-emoji emoji-id="5188153943326208607">👨‍💻</tg-emoji>'
    e_key  = '<tg-emoji emoji-id="5258204546391351475">🔑</tg-emoji>'
    e_docs = '<tg-emoji emoji-id="5902056028513505203">📚</tg-emoji>'
    e_ep   = '<tg-emoji emoji-id="5893102202817352158">⚡</tg-emoji>'
    e_warn = '<tg-emoji emoji-id="5188153943326208607">⚠️</tg-emoji>'

    text = (
        f"{e_api} <b>API для Разработчиков</b>\n\n"
        f"<b>Интегрируй Saint's SMS в свой софт — покупай номера, получай SMS, управляй балансом через HTTP.</b>\n\n"
        f"<b>━━━━━━━━━━━</b>\n"
        f"{e_key} <b>Твой API ключ:</b>\n"
        f"<code>{api_key}</code>\n\n"
        f"<b>━━━━━━━━━━━</b>\n"
        f"{e_ep} <b>Доступные эндпоинты:</b>\n"
        f"<b>├ GET  /api/v1/balance</b> — баланс\n"
        f"<b>├ GET  /api/v1/services</b> — все сервисы\n"
        f"<b>├ GET  /api/v1/countries</b> — страны для сервиса\n"
        f"<b>├ GET  /api/v1/prices</b> — цены по стране и сервису\n"
        f"<b>├ POST /api/v1/buy</b> — купить номер\n"
        f"<b>├ GET  /api/v1/orders</b> — список заказов\n"
        f"<b>├ GET  /api/v1/check/{{order_id}}</b> — статус и SMS\n"
        f"<b>└ POST /api/v1/cancel/{{order_id}}</b> — отмена + возврат\n\n"
        f"<b>━━━━━━━━━━━</b>\n"
        f"{e_docs} <b>Документация (Swagger UI):</b>\n"
        f"<b>└ <a href='{docs_url}'>shopup.sbs/docs</a></b>\n\n"
        f"{e_warn} <b>Никому не передавай свой ключ!</b>"
    )

    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton("🔄 Обновить ключ", callback_data="refresh_api_key"),
        types.InlineKeyboardButton("📚 Документация", url=docs_url)
    )
    keyboard.add(types.InlineKeyboardButton("Назад", callback_data="profile"))

    await call.message.answer(text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)


@dp.callback_query_handler(lambda c: c.data == "refresh_api_key", state="*")
async def refresh_api_key_callback(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    await database.generate_api_key(user_id)
    await call.answer("✅ API ключ успешно обновлён!", show_alert=True)
    await api_menu_callback(call, state)

@dp.callback_query_handler(lambda c: c.data == "faq", state="*")
async def faq_callback(call: types.CallbackQuery, state: FSMContext):
    """
    Обработчик кнопки FAQ
    """
    await state.finish()
    try:
        await call.message.delete()
    except Exception:
        pass
    
    faq_text = get_faq_text()
    keyboard = create_faq_keyboard()
    
    await call.message.answer(faq_text, reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query_handler(lambda c: c.data == "shop", state="*")
async def shop_callback(call: types.CallbackQuery, state: FSMContext):
    """
    Обработчик кнопки Получить номер
    """
    await state.finish()
    try:
        await call.message.delete()
    except Exception:
        pass
    
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    keyboard.add(types.InlineKeyboardButton(text="Активация", callback_data="activation_menu"))
    keyboard.add(types.InlineKeyboardButton(text="Аренда", callback_data="hosting_menu"))
    keyboard.add(types.InlineKeyboardButton(text="Назад", callback_data="back_to_main"))
    
    message_text = "<b>Выберите тип услуги:</b>"
    
    from bin.banners import BANNER_SHOP
    try:
        with open(BANNER_SHOP, 'rb') as photo:
            await call.message.answer_photo(photo, caption=message_text, reply_markup=keyboard, parse_mode="HTML")
    except FileNotFoundError:
        await call.message.answer(message_text, reply_markup=keyboard, parse_mode="HTML")


@dp.callback_query_handler(lambda c: c.data == "back_to_main", state="*")
async def back_to_main_callback(call: types.CallbackQuery, state: FSMContext):
    """
    Обработчик кнопки Вернуться в главное меню
    """
    await state.finish()
    try:
        await call.message.delete()
    except Exception:
        pass
    
    from bin.banners import get_main_menu_text, create_main_menu_keyboard, BANNER_MAIN
    
    message_text = get_main_menu_text(call.from_user.username)
    inline_keyboard = create_main_menu_keyboard()
    
    try:
        with open(BANNER_MAIN, 'rb') as photo:
            await call.message.answer_photo(photo, caption=message_text, reply_markup=inline_keyboard, parse_mode="Markdown")
    except FileNotFoundError:
        await call.message.answer(message_text, reply_markup=inline_keyboard, parse_mode="Markdown")


@dp.callback_query_handler(lambda c: c.data == "last_purchases", state="*")
async def last_purchases_callback(call: types.CallbackQuery, state: FSMContext):
    """
    Обработчик кнопки Последние покупки
    """
    # Не сбрасываем состояние, так как это может быть частью флоу профиля? 
    # Но для безопасности лучше сбросить или оставить как есть.
    # В данном случае это просмотр, так что можно сбросить.
    await state.finish()
    try:
        await call.message.delete()
    except Exception:
        pass
    
    user_id = call.from_user.id
    purchases = await database.get_user_buy(user_id)
    
    if not purchases:
        await call.message.answer("***📦 У вас пока нет покупок***", parse_mode="Markdown")
        return
    
    # Показываем последние 10 покупок
    recent_purchases = purchases[-10:] if len(purchases) > 10 else purchases
    
    text = "<tg-emoji emoji-id=\"5258204546391351475\">🛍</tg-emoji> <b>Ваши последние покупки:</b>\n\n"
    for purchase in reversed(recent_purchases):
        text += f"▫️ <b>{purchase.item_name}</b> | {purchase.count} шт. | ${purchase.amount} | {purchase.date}\n"
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Назад", callback_data="profile"))
    
    await call.message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@dp.callback_query_handler(lambda c: c.data == "saints_team", state="*")
async def saints_team_callback(call: types.CallbackQuery, state: FSMContext):
    """
    Обработчик кнопки Saints Team
    (Оставлен для совместимости, но кнопка теперь ведет по URL)
    """
    await state.finish()
    try:
        await call.message.delete()
    except Exception:
        pass
    # Перенаправляем или пишем ссылку, если вдруг старая кнопка осталась
    await call.message.answer("***Переходите в нашего бота: @SaintsTeamRoBot***", parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data == "help", state="*")
async def help_callback(call: types.CallbackQuery, state: FSMContext):
    """
    Обработчик кнопки Помощь
    """
    await state.finish()
    try:
        await call.message.delete()
    except Exception:
        pass
    
    help_text = "***❓ Помощь***\n\n" \
                "***Если у вас возникли вопросы или проблемы, обратитесь в поддержку:***\n\n" \
                "***• Напишите нам в личные сообщения***\n" \
                "***• Опишите вашу проблему подробно***\n" \
                "***• Мы ответим в течение 24 часов***\n\n" \
                "***Частые вопросы:***\n" \
                "***• Как купить товар?***\n" \
                "***• Как проверить оплату?***\n" \
                "***• Что делать если товар не пришел?***"
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Назад к FAQ", callback_data="faq"))
    
    await call.message.answer(help_text, reply_markup=keyboard, parse_mode="Markdown")


# Обработчик проверки оплаты перенесен в payment_callback.py


# Тестовый обработчик для проверки работы callback'ов
@dp.callback_query_handler(lambda c: c.data == "test_callback")
async def test_callback_handler(call: types.CallbackQuery):
    """
    Тестовый обработчик для проверки работы callback'ов
    """
    logger.info("ТЕСТ: Обработчик test_callback сработал!")
    print("ТЕСТ: Обработчик test_callback сработал!")
    await call.answer("✅ Тестовый обработчик работает!")
    await call.message.answer("🎉 Callback'и работают!")


# Логируем регистрацию обработчиков
logger.info("Регистрируем обработчики в main_callback.py")
print("Регистрируем обработчики в main_callback.py")
