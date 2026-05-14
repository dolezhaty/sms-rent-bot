from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State

import database
from loader import dp
from bin.items.item_loader import add_data
from src import config
from src.const import is_const
from bin.keyboards import cancel_keyboard


class ItemCreator(StatesGroup):
    item_name = State()
    item_desc = State()
    item_pic = State()
    item_price = State()

    item_data = State()


async def add_name(message: types.Message, category_data):
    """
    Запрос названия товара

    :param message:
    :param category_data: данные о категориях
    :return:
    """
    await message.answer("📙 Введите название товара", reply_markup=cancel_keyboard)
    await ItemCreator.item_name.set()

    data = category_data.split("|")

    state = Dispatcher.get_current().current_state()
    await state.update_data(category=data[0])
    await state.update_data(subcategory=data[1])


@dp.message_handler(state=ItemCreator.item_name)
async def add_desc(message: types.Message, state: FSMContext):
    """
    Запрос описания товара
    Добавление названия товара в state

    :param message:
    :param state:
    :return:
    """
    item_name = message.text
    if is_const(item_name):
        await message.answer("❗️ Некорректное значение")
        return

    await state.update_data(name=item_name)
    await ItemCreator.next()
    await message.answer("📋 Введите описание товара")


@dp.message_handler(state=ItemCreator.item_desc)
async def add_pic(message: types.Message, state: FSMContext):
    """
    Запрос картинки товара
    Добавление описания товара в state

    :param message:
    :param state:
    :return:
    """
    item_desc = message.text
    if is_const(item_desc):
        await message.answer("❗️ Некорректное значение")
        return

    await state.update_data(desc=item_desc)
    await ItemCreator.next()
    await message.answer("📷 Загрузите изображение или видео товара (JPG, PNG, MP4)\n\nДля пропуска напишите <i>любой текст</i>")


@dp.message_handler(state=ItemCreator.item_pic, content_types=['photo', 'video', 'text'])
async def add_price(message: types.Message, state: FSMContext):
    """
    Запрос цены товара
    Добавление пути картинки или видео товара в state

    :param message:
    :param state:
    :return:
    """
    item_pic = ""

    if len(message.photo) > 0:
        # Обработка изображения
        src = "items"
        config.create_folder(src)
        item_data = await state.get_data()
        item_name = item_data["name"]
        item_pic = f"{src}/{item_name}.jpg"
        await message.photo[-1].download(item_pic)
    elif message.video:
        # Обработка видео
        src = "items"
        config.create_folder(src)
        item_data = await state.get_data()
        item_name = item_data["name"]
        item_pic = f"{src}/{item_name}.mp4"
        await message.video.download(item_pic)

    await state.update_data(pic=item_pic)

    await ItemCreator.next()
    await message.answer("💵 Введите цену товара в рублях")


@dp.message_handler(state=ItemCreator.item_price)
async def check_price(message: types.Message, state: FSMContext):
    """
    Проверка цены товара
    Запрос данных товара

    :param message:
    :param state:
    :return:
    """
    if not message.text.isdigit():
        await message.answer("❗️ Некорректное значение")
        return

    await state.update_data(price=int(message.text))
    item_data = await state.get_data()

    await state.finish()

    item_name = item_data["name"]
    item = await database.add_item(item_data)

    await message.answer(f"✅ Товар <b>{item_name}</b> создан")

    item_id = item.id
    await add_data(message, item_id)
