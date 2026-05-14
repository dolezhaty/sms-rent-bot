import collections

from aiogram import types
from aiogram.dispatcher.filters import IDFilter

import database
from bin import keyboards
from bin.users import user_finder
from bin.keyboards import create_list_keyboard
from bin.mailing import new_mailing
from bin.statisctic import get_sort_sales_keyboard
from bin.strings import format_stat, get_user_link
from loader import dp
from src.config import ADMIN_ID
from src.const import *


# # # Управление товарами и категориями # # #

@dp.message_handler(IDFilter(chat_id=ADMIN_ID), regexp=const_ru["items"])
async def item_management(message: types.Message):
    """
    Управление товарами

    :param message:
    :return:
    """
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(const_ru["item_management"], const_ru["category_management"])
    keyboard.row(const_ru["back"])

    await message.answer(message.text, reply_markup=keyboard)


@dp.message_handler(IDFilter(chat_id=ADMIN_ID), regexp=const_ru["category_management"])
async def category_management(message: types.Message):
    """
    Управление категориями

    :param message:
    :return:
    """
    keyboard = await keyboards.create_category_keyboard("edit_category")

    keyboard.row(types.InlineKeyboardButton(text=const_ru["add_category"],
                                            callback_data="add_category=-1"))

    keyboard.add(keyboards.CLOSE_BTN)

    await message.answer("📂 Все доступные категории", reply_markup=keyboard)


@dp.message_handler(IDFilter(chat_id=ADMIN_ID), regexp=const_ru["item_management"])
async def item_management(message: types.Message):
    """
    Управление товарами

    :param message:
    :return:
    """
    keyboard = await keyboards.create_category_keyboard("get_item_category")
    keyboard.add(keyboards.CLOSE_BTN)
    await message.answer(const_ru["item_management"], reply_markup=keyboard)


# # # О магазине # # #

@dp.message_handler(IDFilter(chat_id=ADMIN_ID), regexp=const_ru['about_shop'])
async def about_shop(message: types.Message):
    """
    Сведения о магазине

    :param message:
    :return:
    """
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(const_ru["items"], const_ru["payment"])
    # keyboard.row(const_ru["faq"], const_ru["rules"]) # Убрано, так как редактирование отключено
    # keyboard.row(const_ru["hello_message"], const_ru["comeback_message"]) # Убрано
    keyboard.row(const_ru["back"])
    await message.answer(const_ru['about_shop'], reply_markup=keyboard)


# # # Рассылки # # #

@dp.message_handler(IDFilter(chat_id=ADMIN_ID), regexp=const_ru['mailing'])
async def mailing(message: types.Message):
    """
    Меню создания рассылки

    :param message:
    :return:
    """
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(const_ru['create_mailing'])
    keyboard.row(const_ru["back"])
    await message.answer(const_ru['mailing'], reply_markup=keyboard)


@dp.message_handler(IDFilter(chat_id=ADMIN_ID), regexp=const_ru['create_mailing'])
async def create_mailing(message: types.Message):
    """
    Создание рассылки

    :param message:
    :return:
    """
    await new_mailing(message)


# # # Оплата # # #

@dp.message_handler(IDFilter(chat_id=ADMIN_ID), regexp=const_ru["payment"])
async def payment_edit(message: types.Message):
    """
    Управление оплатой

    :param message:
    :return:
    """
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(const_ru["back"])
    await message.answer(message.text, reply_markup=keyboard)


# # # Статистика # # #

@dp.message_handler(IDFilter(chat_id=ADMIN_ID), regexp=const_ru["statistic"])
async def statistics(message: types.Message):
    """
    Статистика

    :param message:
    :return:
    """
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(const_ru["general"], const_ru["daily"])
    keyboard.row(const_ru["back"])

    await message.answer(const_ru["statistic"], reply_markup=keyboard)


@dp.message_handler(IDFilter(chat_id=ADMIN_ID), regexp=const_ru["general"])
async def general(message: types.Message):
    """
    Общая статистика

    :param message:
    :return:
    """
    all_users = await database.get_all_users()

    message_text = f"🏪 Статистика магазина\n" \
                   f"🙍‍♂ Количество участников: <b>{len(all_users)} чел.</b>\n"

    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(types.InlineKeyboardButton(text=const_ru['all_users'], callback_data="all_users_stat"),
                 types.InlineKeyboardButton(text=const_ru['all_purchases'], callback_data="all_purchases_stat"))
    keyboard.add(keyboards.CLOSE_BTN)
    await message.answer(message_text, reply_markup=keyboard)


@dp.message_handler(IDFilter(chat_id=ADMIN_ID), regexp=const_ru["daily"])
async def daily(message: types.Message):
    """
    Ежедневная статистика

    :param message:
    :return:
    """
    await message.answer(const_ru["daily"], reply_markup=await get_sort_sales_keyboard(0))


# # # Пользователи # # #

@dp.message_handler(IDFilter(chat_id=ADMIN_ID), regexp=const_ru["users"])
async def users(message: types.Message):
    """
    Пользователи магазина

    :param message:
    :return:
    """
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(const_ru['find_user'])
    keyboard.row(const_ru['back'])
    await message.answer(const_ru["users"], reply_markup=keyboard)


@dp.message_handler(IDFilter(chat_id=ADMIN_ID), regexp=const_ru['find_user'])
async def find_user(message: types.Message):
    """
    Поиск пользователя

    :param message:
    :return:
    """
    await user_finder.get_user_id(message)
