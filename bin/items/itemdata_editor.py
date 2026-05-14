from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State

import database
from loader import dp
from src import config


class ItemDataEditor(StatesGroup):
    item_data = State()


async def input_item_data(message: types.Message, data_id):
    """
    Запрос новых данных товара

    :param message:
    :param data_id: id позиции товара
    :return:
    """
    await message.answer("📝 Введите новые данные товара, или <b>загрузите файл</b>")

    await ItemDataEditor.item_data.set()
    state = Dispatcher.get_current().current_state()

    item_data_obj = await database.get_data(data_id)
    item_id = item_data_obj.item_id
    await state.update_data(item_id=item_id)
    await state.update_data(data_id=data_id)


@dp.message_handler(state=ItemDataEditor.item_data, content_types=['document', 'text'])
async def load_item(message: types.Message, state: FSMContext):
    """
    Загрузка товара

    :param message:
    :param state:
    :return:
    """
    data = await state.get_data()

    if message.document is not None:
        # документ
        src = "items"
        config.create_folder(src)

        src += f"/{data['item_id']}"
        config.create_folder(src)

        document = message.document
        src += f"/{document['file_name']}"
        await message.document.download(destination=src)

        item_data = f"file={src}"
    else:
        # текст
        item_data = f"text={message.text}"

    await database.update_item_data(data['data_id'], item_data)

    await state.finish()
    await message.answer("✅ Товар обновлен")

    from bin.items.item_editor import get_item_data_info
    await get_item_data_info(message, data['data_id'])
