"""
Модуль для работы с баннерами и изображениями бота
"""

import os
from src.config import DIR

# Пути к изображениям
BANNER_MAIN = f"{DIR}/images/главное меню.jpg"
BANNER_SHOP = f"{DIR}/images/купить.jpg"
BANNER_PROFILE = f"{DIR}/images/профиль.jpg"

def get_main_menu_text(username):
    """
    Получение текста главного меню
    """
    # Текст приветствия теперь задается здесь, а не в БД
    return f"***Добро пожаловать в Saint's SMS Service, @{username}***"

async def get_profile_text(user_data):
    """
    Получение текста профиля с кликабельными элементами (все жирным шрифтом и курсивом)
    """
    import database
    
    # Теперь user_data это объект ORM
    username = user_data.username if user_data.username else "Не указан"
    user_id = user_data.user_id
    balance = user_data.balance
    reg_date = user_data.regDate if user_data.regDate else "Не указана"
    reg_time = user_data.regTime if user_data.regTime else "00:00:00"
    
    # Получаем статистику покупок
    purchases = await database.get_user_buy(user_id)
    total_bought_items = sum(p.count for p in purchases) if purchases else 0
    total_spent_money = sum(p.amount for p in purchases) if purchases else 0
    
    # Баланс и траты теперь в USD
    try:
        balance_usd = float(balance)
    except:
        balance_usd = 0.0

    try:
        spent_usd = float(total_spent_money)
    except:
        spent_usd = 0.0
    
    # Custom Emojis
    # User: 5188153943326208607
    # Balance: 5258204546391351475
    # Cart: 5902056028513505203
    # Reg: 5893102202817352158
    
    e_user = '<tg-emoji emoji-id="5188153943326208607">👤</tg-emoji>'
    e_bal = '<tg-emoji emoji-id="5258204546391351475">💵</tg-emoji>'
    e_cart = '<tg-emoji emoji-id="5902056028513505203">🛒</tg-emoji>'
    e_reg = '<tg-emoji emoji-id="5893102202817352158">⏰</tg-emoji>'

    return f"{e_user} <b>Юзер: @{username}</b>\n" \
           f"<b>└ ID: {user_id}</b>\n" \
           f"<b>━━━━━━━━━━━</b>\n" \
           f"{e_bal} <b>Текущий баланс: ${round(balance_usd, 2)}</b>\n" \
           f"<b>└ {e_cart} Всего куплено товаров: {total_bought_items}</b>\n" \
           f"<b>└ Потрачено в сервисе: ${round(spent_usd, 2)}</b>\n" \
           f"<b>━━━━━━━━━━━</b>\n" \
           f"{e_reg} <b>Регистрация: {reg_date}</b>\n" \
           f"<b>└ Время: {reg_time}</b>"

def get_faq_text():
    """
    Получение текста FAQ
    """
    return "***1. Возврат Денежных Средств с Бота (@SaintsSmsBot) не осуществляется.***\n" \
           "***2. Запрещено использование Бота (@SaintsSmsBot) в любых противоправных целях.***\n" \
           "***3. Мы не несём ответственность за блокировку аккаунтов.***\n" \
           "***4. Если вы ввели номер, а он оказался заблокированный до получения кода, вы должны отменить номер в боте и средства зачислятся на ваш баланс. Если код получен - номер считается использованным.***\n" \
           "***5. Пользуясь Ботом (@SaintsSmsBot) вы соглашаетесь на получение Рекламных Материалов***\n" \
           "***6. Мы не несем ответственности за созданные аккаунты, все действия, включая возможные блокировки.***\n" \
           "***7. Возврат денежных средств за ошибки пользователей - не предусмотрен***\n\n" \
           "***Используя Бота (@SaintsSmsBot) вы автоматически соглашаетесь с правилами. Не знание правил не освобождает от ответственности!***\n\n" \
           "***В случае возникновения проблем - обращайтесь в поддержку: @alyxxxme, @vinted_enjoyer***"

def create_profile_keyboard():
    """
    Создание клавиатуры для профиля
    """
    from aiogram import types
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton("Пополнить баланс", callback_data="add_balance"),
        types.InlineKeyboardButton("Последние покупки", callback_data="last_purchases")
    )
    keyboard.row(
        types.InlineKeyboardButton("Реферальная система", callback_data="referral_menu"),
        types.InlineKeyboardButton("API для Разработчиков", callback_data="api_menu")
    )
    keyboard.row(
        types.InlineKeyboardButton("Назад", callback_data="back_to_main")
    )
    
    return keyboard

def create_faq_keyboard():
    """
    Создание клавиатуры для FAQ
    """
    from aiogram import types
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton("❓ Помощь", callback_data="help"),
        types.InlineKeyboardButton("⬅ Вернуться", callback_data="back_to_main")
    )
    return keyboard

def create_main_menu_keyboard():
    """
    Создание клавиатуры главного меню
    """
    from aiogram import types
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton("Получить номер", callback_data="shop"),
        types.InlineKeyboardButton("Профиль", callback_data="profile")
    )
    keyboard.row(
        types.InlineKeyboardButton("FAQ", callback_data="faq")
    )
    keyboard.row(
        types.InlineKeyboardButton("prod by: Saints Team", url="https://t.me/SaintsTeamRoBot")
    )
    return keyboard
