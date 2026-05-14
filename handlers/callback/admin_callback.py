import collections

from aiogram import types
from aiogram.dispatcher.filters import IDFilter, Regexp

import database
from bin import category, keyboards
from bin.items import item_creator
from bin.items.item_editor import edit_item_menu
from bin.keyboards import create_list_keyboard
from bin.params import input_param_value
# Удалены импорты старых способов оплаты - используется только CryptoBot
# Удален импорт yoo_money
from bin.statisctic import get_sort_sales_keyboard
from bin.strings import get_user_link, format_stat
# from bin.support.support_admin import get_answer
from handlers.message.admin_message import category_management, item_management
from loader import dp
from src.config import ADMIN_ID
from src.const import const_ru


# # # Категории # # #

@dp.callback_query_handler(IDFilter(chat_id=ADMIN_ID), Regexp("get_category_management"))
async def get_category_management(call: types.CallbackQuery):
    """
    Вывод всех категорий для редактирования

    :param call:
    :return:
    """
    await call.message.delete()
    await category_management(call.message)


@dp.callback_query_handler(IDFilter(chat_id=ADMIN_ID), Regexp("add_category"))
async def add_category(call: types.CallbackQuery):
    """
    Добавление категории

    :param call:
    :return:
    """
    data = call.data.split("=")

    await call.message.delete()
    await category.add_name(call.message, data[1])


@dp.callback_query_handler(IDFilter(chat_id=ADMIN_ID), Regexp("edit_category"))
async def edit_category(call: types.CallbackQuery):
    """
    Управление категорией

    :param call:
    :return:
    """
    await call.message.delete()

    data = call.data.split("=")
    category_info = await database.get_category(data[1])
    subcategories = await database.get_subcategories(data[1])

    message_text = f"📁 Категория: <b>{category_info.name}</b>\n" \
                   f"Доступные подкатегории:\n"

    for subcategory in subcategories:
        message_text += f"▫ {subcategory.name}\n"

    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(types.InlineKeyboardButton(text=const_ru["add_subcategory"],
                                            callback_data=f"add_category={data[1]}"),
                 types.InlineKeyboardButton(text=const_ru["delete_subcategory"],
                                            callback_data=f"delete_subсat_select={data[1]}"))

    keyboard.row(types.InlineKeyboardButton(text=const_ru["delete_category"],
                                            callback_data=f"delete_category={data[1]}"))

    keyboard.row(types.InlineKeyboardButton(text=const_ru["back"],
                                            callback_data=f"get_category_management"),
                 keyboards.CLOSE_BTN)

    message_text += "\n❗ При удалении категории/подкатегории, " \
                    "удаляются <b>все товары/категории находящиеся в ней</b>"
    await call.message.answer(message_text, reply_markup=keyboard)


@dp.callback_query_handler(IDFilter(chat_id=ADMIN_ID), Regexp("delete_category"))
async def delete_category(call: types.CallbackQuery):
    """
    Удаление категории

    :param call:
    :return:
    """
    await call.message.delete()
    data = call.data.split("=")
    await database.delete_category(data[1])
    await call.message.answer("✅ Категория удалена")


@dp.callback_query_handler(IDFilter(chat_id=ADMIN_ID), Regexp("delete_subсat_select"))
async def delete_subcategory_select(call: types.CallbackQuery):
    """
    Выбор подкатегории для удаления

    :param call:
    :return:
    """
    await call.message.delete()
    data = call.data.split("=")

    keyboard = await keyboards.create_subcategory_keyboard(data[1], "delete_subcategory")

    await call.message.answer("📁 Выберите подкатегорию", reply_markup=keyboard)


@dp.callback_query_handler(IDFilter(chat_id=ADMIN_ID),
                           lambda call: call.data.startswith("delete_subcategory"))
async def delete_subcategory(call: types.CallbackQuery):
    """
    Удаление подкатегории

    :param call:
    :return:
    """
    await call.message.delete()
    data = call.data.split("=")
    await database.delete_subcategory(data[1])
    await call.message.answer("✅ Податегория удалена")


# # # Товары # # #

@dp.callback_query_handler(IDFilter(chat_id=ADMIN_ID), Regexp("get_item_management"))
async def get_item_management(call: types.CallbackQuery):
    """
    Вернуться ко всем категориям в меню редактирования товаров

    :param call:
    :return:
    """
    await call.message.delete()
    await item_management(call.message)


@dp.callback_query_handler(IDFilter(chat_id=ADMIN_ID), Regexp("get_item_category"))
async def get_item_category(call: types.CallbackQuery):
    """
    Все доступные товары и подкатегории в категории

    :param call:
    :return:
    """
    await call.message.delete()

    data = call.data.split("=")
    keyboard = await keyboards.create_category_items_keyboard(data[1], "get_item_subcategory", "get_item")
    keyboard.add(types.InlineKeyboardButton(text=const_ru["add_item"],
                                            callback_data=f"add_item={data[1]}|0"))
    keyboard.add(types.InlineKeyboardButton(text=const_ru["back"], callback_data="get_item_management"))
    keyboard.add(keyboards.CLOSE_BTN)

    await call.message.answer("📦 Доступные товары и подкатегории\n\n"
                              "📝 Для редактирования товара <i>нажмите на него</i>",
                              reply_markup=keyboard)


@dp.callback_query_handler(IDFilter(chat_id=ADMIN_ID), Regexp("get_item_subcategory"))
async def get_item_subcategory(call: types.CallbackQuery):
    """
    Все доступные товары в подкатегории

    :param call:
    :return:
    """
    await call.message.delete()

    data = call.data.split("=")

    categories = data[1].split("|")

    keyboard = await keyboards.create_subcategory_items_keyboard(categories[0], categories[1], "get_item")
    keyboard.add(types.InlineKeyboardButton(text=const_ru["add_item"],
                                            callback_data=f"add_item={categories[0]}|{categories[1]}"))
    keyboard.row(types.InlineKeyboardButton(text=const_ru["back"],
                                            callback_data=f"get_item_category={categories[0]}"),
                 types.InlineKeyboardButton(text=const_ru["to_all_category"],
                                            callback_data="get_item_management"))
    keyboard.add(keyboards.CLOSE_BTN)

    await call.message.answer("📦 Доступные товары\n\n"
                              "📝 Для редактирования товара <i>нажмите на него</i>",
                              reply_markup=keyboard)


@dp.callback_query_handler(IDFilter(chat_id=ADMIN_ID), Regexp("get_item"))
async def get_item(call: types.CallbackQuery):
    """
    Выбор товара для редактирования

    :param call:
    :return:
    """
    await call.message.delete()
    item_id = call.data.split("=")[1]
    await edit_item_menu(call.message, item_id)


@dp.callback_query_handler(IDFilter(chat_id=ADMIN_ID), Regexp("add_item"))
async def add_item(call: types.CallbackQuery):
    """
    Добавление товара

    :param call:
    :return:
    """
    await call.message.delete()

    data = call.data.split("=")
    await item_creator.add_name(call.message, data[1])


# # # Кошельки - УДАЛЕНО (Используется только CryptoBot) # # #

# Обработчики редактирования Qiwi/YooMoney/Banker удалены,
# так как эти методы оплаты больше не поддерживаются, а функции БД для них удалены.

# # # Прочее # # #

# Обработчики редактирования текстов (FAQ, Rules, Hello) удалены,
# так как тексты перенесены в код/конфиг для оптимизации.



# # # Обращения - УДАЛЕНО # # #

# Функционал поддержки (тикетов) удален в ходе рефакторинга.
# Используйте внешний сервис или бота обратной связи.

# # # Статистика # # #

@dp.callback_query_handler(IDFilter(chat_id=ADMIN_ID), Regexp("all_users_stat"))
async def all_users_stat(call: types.CallbackQuery):
    """
    Статистика по пользователям

    :param call:
    :return:
    """
    await call.message.delete()
    all_sales = await database.get_all_sales()

    best_buyer = collections.defaultdict(int)

    for sale in all_sales:
        link = await get_user_link(sale.user_id)
        best_buyer[f"{link}"] += 1

    buyer_data = format_stat(best_buyer)

    message_text = f"🙍‍♂ Активные покупатели:\n{buyer_data}" \
                   f"➖➖➖➖➖➖➖➖➖➖"
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(keyboards.CLOSE_BTN)
    await call.message.answer(message_text, reply_markup=keyboard)


@dp.callback_query_handler(IDFilter(chat_id=ADMIN_ID), Regexp("all_purchases_stat"))
async def all_purchases_stat(call: types.CallbackQuery):
    """
    Статистика покупок

    :param call:
    :return:
    """
    await call.message.delete()
    all_sales = await database.get_all_sales()
    best_seller = collections.defaultdict(int)

    for sale in all_sales:
        best_seller[sale.item_name] += 1

    sale_data = format_stat(best_seller)

    message_text = f"💰 Сумма всех покупок: <b>${sum(row.amount for row in all_sales)}</b>\n" \
                   f"➖➖➖➖➖➖➖➖➖➖\n" \
                   f"🛒 Часто покупаемые товары:\n{sale_data}" \
                   f"➖➖➖➖➖➖➖➖➖➖\n"
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(keyboards.CLOSE_BTN)
    await call.message.answer(message_text, reply_markup=keyboard)


@dp.callback_query_handler(IDFilter(chat_id=ADMIN_ID), Regexp("daily_stat"))
async def daily_stat(call: types.CallbackQuery):
    """
    Страницы по дневной стате

    :param call:
    :return:
    """
    await call.message.delete()
    call_data = call.data.split("=")

    await call.message.answer(const_ru["daily"], reply_markup=await get_sort_sales_keyboard(call_data[1]))


@dp.callback_query_handler(IDFilter(chat_id=ADMIN_ID), Regexp("get_daily"))
async def get_daily_stat(call: types.CallbackQuery):
    """
    Статистика за день

    :param call:
    :return:
    """
    await call.message.delete()
    call_data = call.data.split("=")[1].split("|")

    daily_sales = await database.get_daily_sales(call_data[0])
    last_index = int(call_data[1])
    limit = last_index + 10

    buyer_list = []
    sum_sales = 0
    sales = ""

    btn_list = []
    if last_index > 10:
        btn_list.append(types.InlineKeyboardButton(
            text=const_ru['back'], callback_data=f"get_daily={call_data[0]}|{(last_index - 10)}"
        ))

    while last_index < limit and last_index < len(daily_sales):
        sale = daily_sales[last_index]

        if sale.user_id not in buyer_list:
            link = await get_user_link(sale.user_id)
            sales += f"{link}\n"

            for other_sale in daily_sales:
                if other_sale.user_id == sale.user_id:
                    sales += f"▫ {other_sale.item_name} | {other_sale.count} шт. | ${other_sale.amount}\n"
                    sum_sales += float(other_sale.amount)

            buyer_list.append(sale.user_id)
            sales += "\n"

        last_index += 1

    if last_index < len(daily_sales):
        btn_list.append(types.InlineKeyboardButton(
            text=const_ru['next'], callback_data=f"get_daily={call_data[0]}|{last_index}"
        ))
    
    users = await database.get_daily_users(call_data[0])
    users_count = len(users)
    
    message_text = f"Статистика за <b>{call_data[0]}</b>\n\n" \
                   f"🙍‍♂ Новые пользователи: <b>{users_count} шт.</b>\n" \
                   f"💰 Прибыль за день: <b>${sum_sales}</b>\n\n" \
                   f"🛒 Покупки:\n\n{sales}"
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(*btn_list)
    keyboard.add(types.InlineKeyboardButton(text=const_ru['return'], callback_data=f"daily_stat={call_data[1]}"))
    keyboard.add(keyboards.CLOSE_BTN)
    await call.message.answer(message_text, reply_markup=keyboard)

