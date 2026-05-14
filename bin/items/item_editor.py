from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Regexp, IDFilter
from aiogram.dispatcher.filters.state import StatesGroup, State

import database
from loader import dp
from bin.items.item_loader import add_data
from bin.items.itemdata_editor import input_item_data
from bin import keyboards
from src.config import ADMIN_ID
from src.const import const_ru, is_const
from bin.keyboards import create_list_keyboard


class ItemEditor(StatesGroup):
    param_pic = State()
    param_value = State()


async def edit_item_menu(message: types.Message, item_id):
    """
    Меню для редактирования товара

    :param message:
    :param item_id: id товара
    :return:
    """
    item = await database.get_item(item_id)
    item_count = await database.get_item_count(item_id)

    message_text = f"📓 Название: <b>{item.name}</b>\n" \
                   f"📋 Описание:\n{item.desc}\n" \
                   f"💳 Цена: {item.price} руб.\n\n" \
                   f"📦 Доступно к покупке: <i>{item_count} шт.</i>"

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text=const_ru["edit_name"],
                                            callback_data=f"edit_item={item_id}|name"))

    keyboard.add(types.InlineKeyboardButton(text=const_ru["edit_desc"],
                                            callback_data=f"edit_item={item_id}|desc"))

    keyboard.add(types.InlineKeyboardButton(text=const_ru["edit_pic"],
                                            callback_data=f"edit_pic={item_id}"))

    keyboard.add(types.InlineKeyboardButton(text=const_ru["edit_price"],
                                            callback_data=f"edit_item={item_id}|price"))

    keyboard.add(types.InlineKeyboardButton(text=const_ru["edit_data"],
                                            callback_data=f"get_data={item_id}|0"))

    keyboard.row(types.InlineKeyboardButton(text=const_ru["load_data"],
                                            callback_data=f"load_data={item_id}"),
                 types.InlineKeyboardButton(text=const_ru["delete_data"],
                                            callback_data=f"delete_all_data={item_id}"))

    keyboard.add(types.InlineKeyboardButton(text=const_ru["delete_item"],
                                            callback_data=f"delete_item={item_id}"))

    if item.subcategory == 0 or item.subcategory is None:
        back_callback = f"get_item_category={item.category}"
    else:
        back_callback = f"get_item_subcategory={item.category}|{item.subcategory}"

    keyboard.row(types.InlineKeyboardButton(text=const_ru["back"],
                                            callback_data=back_callback),
                 types.InlineKeyboardButton(text=const_ru["to_all_category"],
                                            callback_data="get_item_management"))

    keyboard.add(keyboards.CLOSE_BTN)

    if item.pic != "":
        # Проверяем расширение файла
        if item.pic.endswith('.mp4'):
            # Отправляем видео
            await message.answer_video(open(item.pic, "rb"), caption=message_text, reply_markup=keyboard)
        else:
            # Отправляем изображение
            await message.answer_photo(open(item.pic, "rb"), caption=message_text, reply_markup=keyboard)
    else:
        await message.answer(message_text, reply_markup=keyboard)


# # # Управление позициями товара # # #

@dp.callback_query_handler(IDFilter(chat_id=ADMIN_ID), Regexp("get_data"))
async def edit_data(call: types.CallbackQuery):
    """
    Редактирование товара

    :param call:
    :return:
    """
    await call.message.delete()
    call_data = call.data.split("=")
    page_data = call_data[1].split("|")

    keyboard = create_list_keyboard(data=database.get_all_item_data(page_data[0]),
                                    last_index=int(page_data[1]),
                                    page_click=f"get_data={page_data[0]}",
                                    btn_text_param="item_data",
                                    btn_click="item_data",
                                    back_method=f"get_item={page_data[0]}")
    await call.message.answer("📦 Все доступные данные товара", reply_markup=keyboard)


@dp.callback_query_handler(IDFilter(chat_id=ADMIN_ID), Regexp("item_data"))
async def edit_data(call: types.CallbackQuery):
    """
    Редактирование данных

    :param call:
    :return:
    """
    await call.message.delete()
    call_data = call.data.split("=")
    await get_item_data_info(call.message, call_data[1])


async def get_item_data_info(message, item_id):
    """
    Вывод информации о позиции товара

    :param message:
    :param item_id:
    :return:
    """
    item_data = database.get_data(item_id)
    item_type = item_data[2].split("=")

    if item_type[0] == "text":
        type_data = "Текст"
    else:
        type_data = "Файл"

    message_text = f"📋 Тип товара: <b>{type_data}</b>\n📦 Данные:\n\n<b>{item_type[1]}</b>"

    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(types.InlineKeyboardButton(text=const_ru['edit'],
                                            callback_data=f"edit_data={item_id}"),
                 types.InlineKeyboardButton(text=const_ru['delete'],
                                            callback_data=f"delete_data={item_id}"))
    keyboard.add(types.InlineKeyboardButton(text=const_ru['back'],
                                            callback_data=f"get_data={item_data[1]}|0"))
    keyboard.add(keyboards.CLOSE_BTN)
    await message.answer(message_text, reply_markup=keyboard)


@dp.callback_query_handler(IDFilter(chat_id=ADMIN_ID), Regexp("edit_data"))
async def edit_data(call: types.CallbackQuery):
    """
    Редактирование позиции товара

    :param call:
    :return:
    """
    await call.message.delete()
    call_data = call.data.split("=")

    await input_item_data(call.message, call_data[1])


@dp.callback_query_handler(IDFilter(chat_id=ADMIN_ID), Regexp("delete_data"))
async def delete_data(call: types.CallbackQuery):
    """
    Удаление позиции товара

    :param call:
    :return:
    """
    await call.message.delete()
    call_data = call.data.split("=")
    item_id = database.get_data(call_data[1])[1]

    database.delete_item_data(call_data[1])

    await call.message.answer("✅ Позиция удалена")
    await edit_item_menu(call.message, item_id)


@dp.callback_query_handler(IDFilter(chat_id=ADMIN_ID), Regexp("load_data"))
async def load_data(call: types.CallbackQuery):
    """
    Дозагрузка данных товара

    :param call:
    :return:
    """
    await call.message.delete()
    item_id = call.data.split("=")[1]
    await add_data(call.message, item_id, True)


@dp.callback_query_handler(IDFilter(chat_id=ADMIN_ID), Regexp("delete_all_data"))
async def delete_data(call: types.CallbackQuery):
    """
    Удаление данных товара

    :param call:
    :return:
    """
    await call.message.delete()
    item_id = call.data.split("=")[1]
    database.delete_all_item_data(item_id)
    await call.message.answer("✅ Данные удалены")
    await edit_item_menu(call.message, item_id)


@dp.callback_query_handler(IDFilter(chat_id=ADMIN_ID), Regexp("delete_item"))
async def delete_item(call: types.CallbackQuery):
    """
    Удалить товар полностью

    :param call:
    :return:
    """
    await call.message.delete()
    item_id = call.data.split("=")[1]
    await database.delete_item(item_id)
    await call.message.answer("✅ Товар удален")


# # # Редактирование параметров товара # # #

@dp.callback_query_handler(IDFilter(chat_id=ADMIN_ID), Regexp("edit_item"))
async def edit_item(call: types.CallbackQuery):
    """
    Редактирование параметров товара

    :param call:
    :return:
    """
    await call.message.delete()
    call_data = call.data.split("=")
    item_param = call_data[1].split("|")

    await input_item_value(call.message, item_param[0], item_param[1])


async def input_item_value(message: types.Message, item_id, param_type):
    """
    Запись значения параментра

    :param message:
    :param item_id: id товара
    :param param_type: тип параметра
    :return:
    """
    await ItemEditor.param_value.set()
    state = Dispatcher.get_current().current_state()
    await state.update_data(item_id=item_id)
    await state.update_data(param=param_type)

    await message.answer("✏️ Введите новое значение")


@dp.message_handler(state=ItemEditor.param_value)
async def update_value(message: types.Message, state: FSMContext):
    """
    Проверка значений

    :param message:
    :param state:
    :return:
    """
    value = message.text
    if is_const(value):
        await message.answer("❗️ Введите корректное значение ❗️")
        return

    await state.update_data(value=value)

    await load_value(message, state)


@dp.callback_query_handler(IDFilter(chat_id=ADMIN_ID), Regexp("edit_pic"))
async def edit_pic(call: types.CallbackQuery):
    """
    Редактирование изображения

    :param call:
    :return:
    """
    await call.message.delete()
    call_data = call.data.split("=")

    await ItemEditor.param_pic.set()
    state = Dispatcher.get_current().current_state()
    await state.update_data(item_id=call_data[1])
    await state.update_data(param="pic")

    await call.message.answer("📷 Загрузите изображение или видео товара (JPG, PNG, MP4)\n\nДля пропуска напишите <i>любой текст</i>")


@dp.message_handler(state=ItemEditor.param_pic, content_types=['photo', 'video', 'text'])
async def check_pic(message: types.Message, state: FSMContext):
    """
    Проверка изображения или видео

    :param message:
    :param state:
    :return:
    """
    item_pic = ""

    if len(message.photo) > 0:
        # Обработка изображения
        src = "items"
        config.create_folder(src)
        data = await state.get_data()
        item_name = database.get_item(data['item_id'])[1]
        item_pic = f"{src}/{item_name}.jpg"
        await message.photo[-1].download(item_pic)
    elif message.video:
        # Обработка видео
        src = "items"
        config.create_folder(src)
        data = await state.get_data()
        item_name = database.get_item(data['item_id'])[1]
        item_pic = f"{src}/{item_name}.mp4"
        await message.video.download(item_pic)

    await state.update_data(value=item_pic)
    await load_value(message, state)


async def load_value(message, state):
    """
    Запись значения в БД

    :param message:
    :param state:
    :return:
    """
    data = await state.get_data()
    item_id = data['item_id']
    param = data['param']
    value = data['value']

    await database.edit_item_param(item_id, param, value)

    await message.answer("✅ Значение изменено")
    await state.finish()
    await edit_item_menu(message, item_id)
