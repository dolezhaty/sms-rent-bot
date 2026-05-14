import os

# Удалены старые способы оплаты - используется только CryptoBot
from src.config import is_admin
from bin.strings import item_format
from src.const import const_ru
from aiogram import types

user_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
user_keyboard.row(const_ru["shop"], const_ru["profile"])
user_keyboard.row(const_ru["faq"])
user_keyboard.row(const_ru["saints_team"])

admin_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
admin_keyboard.row(const_ru["shop"], const_ru["profile"])
admin_keyboard.row(const_ru["faq"])
admin_keyboard.row(const_ru["saints_team"])
admin_keyboard.row(const_ru["about_shop"])
admin_keyboard.row(const_ru["support"])
admin_keyboard.row(const_ru["statistic"], const_ru["users"], const_ru["mailing"])

CLOSE_BTN = types.InlineKeyboardButton(text=const_ru["close"], callback_data="close")

cancel_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
cancel_keyboard.row(const_ru['cancel'])


def get_keyboard_for_finish(user_id):
    """
    Получение клавиатуры после завершения действия

    :param user_id: user id
    :return:
    """
    if is_admin(user_id):
        return admin_keyboard
    else:
        return user_keyboard


async def create_category_keyboard(method):
    """
    Создание клавиатуры с категориями

    :param method: метод для callback_data
    :return:
    """
    import database
    categories = await database.get_categories()

    keyboard = types.InlineKeyboardMarkup()
    for category in categories:
        keyboard.add(types.InlineKeyboardButton(
            text=category.name,
            callback_data=f"{method}={category.id}"
        ))

    return keyboard


async def create_subcategory_keyboard(category_id, method):
    """
    Создание клавиатуры с подкатегориями

    :param category_id: id категории
    :param method: метод для callback_data
    :return:
    """
    import database
    subcategories = await database.get_subcategories(category_id)

    keyboard = types.InlineKeyboardMarkup()
    for subcategory in subcategories:
        keyboard.add(types.InlineKeyboardButton(
            text=subcategory.name,
            callback_data=f"{method}={subcategory.id}"
        ))

    return keyboard


async def create_category_items_keyboard(category_id, method_subcategory, method_item):
    """
    Создание клавиатуры с подкатегориями и товарами в категории

    :param category_id: id категории
    :param method_subcategory: метод категории для callback_data
    :param method_item: метод товара для callback_data
    :return:
    """
    import database

    subcategories = await database.get_subcategories(category_id)

    keyboard = types.InlineKeyboardMarkup()
    for subcategory in subcategories:
        keyboard.add(types.InlineKeyboardButton(
            text=subcategory.name,
            callback_data=f"{method_subcategory}={category_id}|{subcategory.id}"
        ))

    items = await database.get_items_category(category_id, 0)
    for item in items:
        keyboard.add(types.InlineKeyboardButton(
            text=item_format(item),
            callback_data=f"{method_item}={item.id}"
        ))

    return keyboard


async def create_subcategory_items_keyboard(category_id, subcategory_id, method_item):
    """
    Создание клавиатуры с товарами в подкатегории

    :param category_id: id категории
    :param subcategory_id: id подкатегории
    :param method_item: метод товара для callback_data
    :return:
    """
    import database
    keyboard = types.InlineKeyboardMarkup()

    items = await database.get_items_category(category_id, subcategory_id)
    for item in items:
        keyboard.add(types.InlineKeyboardButton(
            text=await item_format(item),
            callback_data=f"{method_item}={item.id}"
        ))

    return keyboard


def get_payment_keyboard():
    """
    Клавиатура с доступными способами оплаты
    :return:
    """
    keyboard = types.InlineKeyboardMarkup()
    
    # Добавляем только CryptoBot
    keyboard.add(types.InlineKeyboardButton(text="💳 CryptoBot", callback_data="payment=cryptobot"))
    
    return keyboard


def create_list_keyboard(data, last_index, page_click: str, btn_text_param, btn_click, back_method=None):
    """
    Создание страничной клавиатуры

    :param data: данные для клавиатуры
    :param last_index: послендий индекс
    :param page_click: метод для нажатия вперед/назад
    :param btn_text_param: текст для кнопки
    :param btn_click: метод для кнопки
    :param back_method: метод для кнопки назад, по умолчанию None
    :return:
    """
    import database
    keyboard = types.InlineKeyboardMarkup()
    btn_list = []

    btn_text = ""

    if page_click.endswith("="):
        callback = f"{page_click}"
    else:
        callback = f"{page_click}|"

    if last_index >= 10:
        btn_list.append(types.InlineKeyboardButton(
            text=const_ru['back'], callback_data=f"{callback}{(last_index - 10)}"
        ))

    if len(data) > 0:
        limit = last_index + 10

        while last_index < limit and last_index < len(data):
            item = data[last_index]
            
            # Helper to get attribute or index safely
            def get_val(obj, attr, idx):
                return getattr(obj, attr) if hasattr(obj, attr) else (obj[idx] if isinstance(obj, (list, tuple)) else obj)

            item_id = get_val(item, 'id', 0)
            
            click = f"{btn_click}={item_id}"

            if btn_text_param == "support":
                val1 = item_id
                val2 = get_val(item, 'item_name', 1)
                btn_text = f"#{val1} | {val2}"
            elif btn_text_param == "user_support":
                val = get_val(item, 'user_id', 0)
                click = f"{btn_click}={val}"
                btn_text = f"#{val}"
            elif btn_text_param == "item_data":
                val = get_val(item, 'data', 2)
                val = val.split('=')[1] if '=' in val else val
                btn_text = f"{val}"
            elif btn_text_param == "daily_stat":
                btn_text = f"{item}"
                click = f"{btn_click}={item}|0"
            elif btn_text_param == "daily_purchases":
                click = f"{btn_click}={item_id}|{(limit - 10)}"

            keyboard.add(
                types.InlineKeyboardButton(text=btn_text,
                                           callback_data=click)
            )
            last_index += 1

        if last_index < len(data):
            btn_list.append(types.InlineKeyboardButton(
                text=const_ru['next'], callback_data=f"{callback}{last_index}"
            ))

        keyboard.row(*btn_list)

    if back_method is not None:
        keyboard.add(types.InlineKeyboardButton(text=const_ru["back"],
                                                callback_data=back_method))
    keyboard.add(CLOSE_BTN)

    return keyboard
