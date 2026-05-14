from aiogram import types
from aiogram.dispatcher import FSMContext
import database
from bin.banners import get_main_menu_text, create_main_menu_keyboard, BANNER_MAIN, get_profile_text, create_profile_keyboard, BANNER_PROFILE, get_faq_text, create_faq_keyboard, BANNER_SHOP
from src.const import const_ru
from loader import dp

@dp.message_handler(commands=["start"], state="*")
async def user_start(message: types.Message, state: FSMContext):
    await state.finish()
    
    # Добавляем пользователя в БД
    from bin.strings import get_now_date
    from bin.users import user_finder # Нам не нужен user_finder для регистрации
    
    # Пытаемся добавить пользователя
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    
    # Определяем пригласившего (если есть)
    inviting = 0
    args = message.get_args()
    if args:
        if args.isdigit():
            inviting = int(args)
        elif args.startswith("REF") and args[3:].isdigit():
            inviting = int(args[3:])
        
    await database.add_user(user_id, username, first_name, last_name, inviting)
    
    text = get_main_menu_text(message.from_user.username)
    keyboard = create_main_menu_keyboard()
    
    try:
        with open(BANNER_MAIN, 'rb') as photo:
            await message.answer_photo(photo, caption=text, reply_markup=keyboard, parse_mode="Markdown")
    except FileNotFoundError:
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    
    try:
        await message.delete()
    except:
        pass

@dp.message_handler(text=["***📱 Получить номер***", "📱 Получить номер"], state="*")
async def get_number(message: types.Message):
    # This is the "Shop" or "Get Number" button
    await shop_message(message)

@dp.message_handler(text=["***🏪 Магазин***", "🏪 Магазин"], state="*")
async def shop_message(message: types.Message):
    try:
        await message.delete()
    except:
        pass
        
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(types.InlineKeyboardButton(text="Активация", callback_data="activation_menu"))
    keyboard.add(types.InlineKeyboardButton(text="Аренда", callback_data="hosting_menu"))
    keyboard.add(types.InlineKeyboardButton(text="Назад", callback_data="back_to_main"))

    message_text = "<b>Выберите тип услуги:</b>"
    
    try:
        with open(BANNER_SHOP, 'rb') as photo:
            await message.answer_photo(photo, caption=message_text, reply_markup=keyboard, parse_mode="HTML")
    except FileNotFoundError:
        await message.answer(message_text, reply_markup=keyboard, parse_mode="HTML")

@dp.message_handler(text=["***👤 Профиль***", "👤 Профиль"], state="*")
async def profile(message: types.Message):
    try:
        await message.delete()
    except:
        pass
        
    user_data = await database.get_user(str(message.from_user.id))
    if user_data is None:
        await message.answer("***❗️ Пользователь не найден***\n***Пропишите /start для авторизации***", parse_mode="Markdown")
        return

    text = await get_profile_text(user_data)
    keyboard = create_profile_keyboard()
    
    try:
        with open(BANNER_PROFILE, 'rb') as photo:
            await message.answer_photo(photo, caption=text, reply_markup=keyboard, parse_mode="HTML")
    except FileNotFoundError:
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@dp.message_handler(text=["***❓ FAQ***", "❓ FAQ", const_ru["faq"]], state="*")
async def faq(message: types.Message):
    try:
        await message.delete()
    except:
        pass
        
    text = get_faq_text()
    keyboard = create_faq_keyboard()
    
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

@dp.message_handler(text=["***Saints Team***", "Saints Team", const_ru["saints_team"]], state="*")
async def saints_team(message: types.Message):
    try:
        await message.delete()
    except:
        pass
    # Так как это текстовая кнопка, мы не можем сделать её URL-кнопкой напрямую в ReplyKeyboard.
    # Поэтому мы отправляем сообщение с URL-кнопкой или просто ссылкой.
    await message.answer("***Переходите в нашего бота: @SaintsTeamRoBot***", parse_mode="Markdown")

@dp.message_handler(lambda message: "🔍 Поиск сервиса:" in message.text or "🔍 Выбрана страна для Other:" in message.text, state="*")
async def process_inline_search_result(message: types.Message):
    """Обработка выбора сервиса или страны из инлайн-поиска"""
    try:
        await message.delete()
    except:
        pass
        
    text = message.text.replace("***", "")
    
    if "🔍 Выбрана страна для Other:" in text:
        # Формат: "🔍 Выбрана страна для Other: Russia|russia"
        data = text.replace("🔍 Выбрана страна для Other: ", "").strip()
        country_name, country_code = data.split("|")
        
        # Сразу переходим к покупке (показываем операторов) для сервиса 'other'
        from bin.api_5sim import FiveSimAPI
        from bin.pricing import get_final_price_usd
        import re
        
        service = "other"
        prices_data = await FiveSimAPI.get_prices(country=country_code, product=service)
        
        if not prices_data or service not in prices_data:
            await message.answer(f"❌ Нет номеров для сервиса 'Любой другой' в стране {country_name}", parse_mode="HTML")
            return

        operators_data = prices_data[service]
        
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        found_any = False
        
        # Premium Emojis IDs
        s_emoji = '<tg-emoji emoji-id="5260348422266822411">💬</tg-emoji>'
        c_emoji = '<tg-emoji emoji-id="5258509201306557640">📍</tg-emoji>'
        o_emoji = '<tg-emoji emoji-id="5893161718179173515">📶</tg-emoji>'

        for operator, info in operators_data.items():
            cost = info.get('cost')
            count = info.get('count')
            if count and count > 0:
                found_any = True
                
                # Рассчитываем финальную цену в USD
                final_price = get_final_price_usd(float(cost))
                
                # Заменяем технические названия операторов (virtualXX -> Провайдер #XX)
                display_operator = re.sub(r'virtual(\d+)', r'Провайдер #\1', operator)
                
                keyboard.add(types.InlineKeyboardButton(
                    text=f"{display_operator} | {final_price}$ | {count} шт.", 
                    callback_data=f"buy_num={service}|{country_code}|{operator}|{final_price}"
                ))
                
        keyboard.add(types.InlineKeyboardButton(text="Назад", callback_data=f"select_service={service}"))
        
        msg_text = f"<b>{s_emoji} Сервис: Любой другой</b>\n" \
                   f"<b>{c_emoji} Страна: {country_name}</b>\n" \
                   f"<b>{o_emoji} Выберите оператора:</b>"
                   
        if not found_any:
            msg_text += "\n\n<b>😔 Нет доступных номеров.</b>"
        
        await message.answer(msg_text, reply_markup=keyboard, parse_mode="HTML")
        return

    # Извлекаем название сервиса. Формат может быть: "***🔍 Поиск сервиса: service***" или просто "🔍 Поиск сервиса: service"
    # Удаляем Markdown символы и префикс
    service_name = text.replace("🔍 Поиск сервиса: ", "").strip()
    
    # Приводим к нижнему регистру, так как API 5sim чувствителен или мы храним ключи в нижнем
    service_name = service_name.lower()
    
    from handlers.callback.order_callback import show_country_selection
    await show_country_selection(message, service_name, page=0, edit_message=False)
