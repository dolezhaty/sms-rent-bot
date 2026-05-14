import json

from aiogram import types
from aiogram.dispatcher.filters import Regexp

import database
from handlers.message.user_message import shop_message
from loader import dp
from bin.purchase.purchase import select_count
from bin import keyboards
from src.const import const_ru
from bin.keyboards import create_list_keyboard

# # # Товары # # #

@dp.callback_query_handler(Regexp("all_category"))
async def all_category(call: types.CallbackQuery):
    """
    Вызов метода shop_message() из user_message

    :param call:
    :return:
    """
    await call.message.delete()
    await shop_message(call.message)


@dp.callback_query_handler(Regexp("select_category"))
async def select_category(call: types.CallbackQuery):
    """
    Вывод товаров и подкатегорий в выбранной категории

    :param call:
    :return:
    """
    await call.message.delete()

    data = call.data.split("=")
    keyboard = await keyboards.create_category_items_keyboard(data[1], "select_subcategory", "select_item")
    length = len(json.loads(keyboard.as_json())["inline_keyboard"])

    message_text = "🛒 Все доступные товары и подкатегории"
    if length == 0:
        message_text = const_ru["nothing"]

    keyboard.add(types.InlineKeyboardButton(text=const_ru["back"],
                                            callback_data="all_category"))
    keyboard.add(keyboards.CLOSE_BTN)
    await call.message.answer(message_text, reply_markup=keyboard)


@dp.callback_query_handler(Regexp("select_subcategory"))
async def select_subcategory(call: types.CallbackQuery):
    """
    Все товары в выбранной подкатегории

    :param call:
    :return:
    """
    await call.message.delete()

    data = call.data.split("=")[1].split("|")
    keyboard = await keyboards.create_subcategory_items_keyboard(data[0], data[1], "select_item")
    length = len(json.loads(keyboard.as_json())["inline_keyboard"])

    message_text = "🛒 Все доступные товары"
    if length == 0:
        message_text = const_ru["nothing"]

    keyboard.row(types.InlineKeyboardButton(text=const_ru["back"],
                                            callback_data=f"select_category={data[0]}"),
                 types.InlineKeyboardButton(text=const_ru["to_all_category"],
                                            callback_data="all_category"))
    keyboard.add(keyboards.CLOSE_BTN)

    await call.message.answer(message_text, reply_markup=keyboard)


@dp.callback_query_handler(Regexp("select_item"))
async def select_item(call: types.CallbackQuery):
    """
    Информация о выбранном предмете

    :param call:
    :return:
    """
    await call.message.delete()
    data = call.data.split("=")

    item = await database.get_item(data[1])
    item_count = await database.get_item_count(data[1])

    if item is None:
        await call.message.answer("Товар не найден")
        return

    message_text = f"📓 Название: <b>{item.name}</b>\n" \
                   f"📋 Описание:\n{item.desc}\n" \
                   f"💳 Цена: ${item.price}\n\n" \
                   f"📦 Доступно к покупке: <i>{item_count} шт.</i>"

    keyboard = types.InlineKeyboardMarkup()

    if item_count > 0:
        keyboard.add(types.InlineKeyboardButton(text=const_ru["buy"],
                                                callback_data=f"buy_item={data[1]}"))
    else:
        message_text += "\n\n <b>❗️ ️ Товар временно отсутствует️️</b>"

    if item.subcategory == 0:
        back_callback = f"select_category={item.category}"
    else:
        back_callback = f"select_subcategory={item.category}|{item.subcategory}"

    keyboard.row(types.InlineKeyboardButton(text=const_ru["back"],
                                            callback_data=back_callback),
                 types.InlineKeyboardButton(text=const_ru["to_all_category"],
                                            callback_data="all_category"))

    keyboard.add(keyboards.CLOSE_BTN)
    if item.pic != "":
        # Проверяем расширение файла
        if item.pic.endswith('.mp4'):
            # Отправляем видео
            await call.message.answer_video(open(item.pic, "rb"), caption=message_text, reply_markup=keyboard)
        else:
            # Отправляем изображение
            await call.message.answer_photo(open(item.pic, "rb"), caption=message_text, reply_markup=keyboard)
    else:
        await call.message.answer(message_text, reply_markup=keyboard)


@dp.callback_query_handler(Regexp("buy_item"))
async def buy_item(call: types.CallbackQuery):
    """
    Обработка покупки товара

    :param call:
    :return:
    """
    await call.message.delete()
    data = call.data.split("=")

    await select_count(call.message, data[1])


# # # Обращения - УДАЛЕНО # # #

