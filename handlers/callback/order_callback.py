from aiogram import types
from aiogram.dispatcher import FSMContext
from loader import dp, bot
from bin.api_5sim import FiveSimAPI
from bin.keyboards import CLOSE_BTN
from bin.states import BotStates
from src.const import const_ru
from bin.country_utils import get_country_sort_key, get_country_info
import database
import logging

logger = logging.getLogger(__name__)

# In-memory lock for cancellations to prevent race conditions
processing_cancellations = set()
# Keep track of refunded orders to prevent double refunds (in-memory, per session)
refunded_orders = set()

async def get_updated_price(service: str, country: str, operator: str) -> float:
    """
    Получает актуальную цену от 5sim и рассчитывает финальную стоимость.
    """
    from bin.pricing import get_final_price_usd
    
    try:
        prices_data = await FiveSimAPI.get_prices(country=country, product=service)
        if not prices_data or service not in prices_data:
            return None
            
        operators_data = prices_data[service]
        
        if operator == 'any':
            # Ищем минимальную цену среди всех операторов с наличием номеров
            min_cost = float('inf')
            for op_name, info in operators_data.items():
                cost = float(info.get('cost', float('inf')))
                count = int(info.get('count', 0))
                if count > 0 and cost < min_cost:
                    min_cost = cost
            
            if min_cost == float('inf'):
                return None
            return get_final_price_usd(min_cost)
        else:
            # Берем цену конкретного оператора
            if operator not in operators_data:
                return None
            
            info = operators_data[operator]
            cost = float(info.get('cost', 0))
            if cost <= 0:
                return None
            return get_final_price_usd(cost)
            
    except Exception as e:
        logger.error(f"Error in get_updated_price: {e}")
        return None

async def show_country_selection(query_or_msg, service: str, page: int = 0, edit_message: bool = True, display_name: str = None):
    """
    Shows country selection menu (Search + Buttons).
    """
    if not display_name:
        display_name = service.capitalize()
        
    # Определяем, пришел нам callback_query или message
    if isinstance(query_or_msg, types.CallbackQuery):
        callback_query = query_or_msg
        message = callback_query.message
    else:
        callback_query = None
        message = query_or_msg

    try:
        countries_list = await FiveSimAPI.get_countries_for_service(service)
    except Exception as e:
        logger.error(f"Error loading countries for {service}: {e}")
        if callback_query:
            await callback_query.answer("Ошибка загрузки стран", show_alert=True)
        return

    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    s_emoji = '<tg-emoji emoji-id="5260348422266822411">💬</tg-emoji>'
    c_emoji = '<tg-emoji emoji-id="5258509201306557640">📍</tg-emoji>'

    if len(countries_list) <= 10:
        # Режим списка (мало стран) - как раньше
        text = f"{s_emoji} <b>Сервис: {service.capitalize()}</b>\n" \
               f"{c_emoji} <b>Выберите страну:</b>"
        
        for code, name in countries_list:
            flag = FiveSimAPI.get_country_flag(code)
            keyboard.insert(types.InlineKeyboardButton(text=f"{flag} {name}", callback_data=f"select_country={service}|{code}"))
            
    else:
        # Режим "Много стран"
        # Проверяем, есть ли пресеты для этого сервиса
        presets = []
        
        if service in ['telegram', 'whatsapp']:
            presets = [
                ('usa', 'england'),
                ('germany', 'spain'),
                ('italy', 'netherlands')
            ]
        elif service == 'ebay': # Kleinanzeigen (мы передаем ebay в callback, поэтому здесь ebay)
             presets = [
                ('germany', 'england'),
                ('poland', 'austria'),
                ('serbia', 'slovakia')
            ]
            
        if presets:
            text = f"{s_emoji} <b>Сервис: {service.capitalize()}</b>\n" \
                   f"{c_emoji} <b>Популярные страны:</b>"
            
            # Предварительно нормализуем список доступных стран для поиска
            # Создаем словарь {normalized_name: (real_code, real_name)}
            # Нормализация: нижний регистр, без пробелов, замена алиасов
            available_countries = {}
            for c_code, c_name in countries_list:
                available_countries[c_code.lower()] = (c_code, c_name)
                # Добавляем маппинг для известных алиасов
                if c_code == 'unitedkingdom': available_countries['england'] = (c_code, c_name)
                if c_code == 'england': available_countries['unitedkingdom'] = (c_code, c_name) # На всякий случай
                if c_code == 'usa': available_countries['unitedstates'] = (c_code, c_name) # 5sim usually uses 'usa' or 'united-states'
                
            for country1, country2 in presets:
                btn1 = None
                btn2 = None
                
                # Функция поиска с учетом алиасов
                def get_btn_data(target):
                    target = target.lower()
                    if target in available_countries:
                        return available_countries[target]
                    # Прямой поиск, если алиас не сработал (вдруг код совпадает)
                    return None

                data1 = get_btn_data(country1)
                data2 = get_btn_data(country2)
                
                # Если страны нет в списке API, мы все равно МОЖЕМ попробовать добавить кнопку,
                # если уверены в коде. Но лучше показывать только доступные.
                # В данном случае, если API не вернул страну, значит номеров нет -> кнопку не показываем.
                
                # ИСКЛЮЧЕНИЕ: Для демонстрации интерфейса, если API вернул странный ответ,
                # или если страны реально нет, но мы хотим показать кнопку (пусть юзер нажмет и узнает, что нет номеров),
                # мы можем добавить fallback.
                
                # Чтобы кнопки ГАРАНТИРОВАННО появились, даже если 5sim тупит с названиями:
                from bin.country_utils import get_country_info
                
                if not data1:
                    # Fallback: пробуем создать кнопку принудительно
                    info = get_country_info(country1)
                    if info:
                        data1 = (country1, info['name'])
                    else:
                        data1 = (country1, country1.title())
                        
                if not data2:
                    info = get_country_info(country2)
                    if info:
                        data2 = (country2, info['name'])
                    else:
                        data2 = (country2, country2.title())

                if data1:
                    c1, n1 = data1
                    flag = FiveSimAPI.get_country_flag(c1)
                    btn1 = types.InlineKeyboardButton(text=f"{flag} {n1}", callback_data=f"select_country={service}|{c1}")
                
                if data2:
                    c2, n2 = data2
                    flag = FiveSimAPI.get_country_flag(c2)
                    btn2 = types.InlineKeyboardButton(text=f"{flag} {n2}", callback_data=f"select_country={service}|{c2}")

                if btn1 and btn2:
                    keyboard.row(btn1, btn2)
                elif btn1:
                    keyboard.add(btn1)
                elif btn2:
                    keyboard.add(btn2)
            
            keyboard.add(types.InlineKeyboardButton(text="🔎 Поиск страны", switch_inline_query_current_chat=f"country {service} "))
            
        else:
            text = f"{s_emoji} <b>Сервис: {service.capitalize()}</b>\n" \
                   f"<b>Нажмите '🔎 Поиск страны', чтобы выбрать страну:</b>"
            keyboard.add(types.InlineKeyboardButton(text="🔎 Поиск страны", switch_inline_query_current_chat=f"country {service} "))
        
    keyboard.add(types.InlineKeyboardButton(text="Назад", callback_data="activation_menu"))
    
    if edit_message:
        try:
            if message:
                try:
                    await message.edit_caption(caption=text, reply_markup=keyboard, parse_mode="HTML")
                except Exception:
                    await message.edit_text(text=text, reply_markup=keyboard, parse_mode="HTML")
            elif callback_query and callback_query.inline_message_id:
                # Если это инлайн-сообщение, используем bot.edit_message_caption/text
                try:
                    await bot.edit_message_caption(inline_message_id=callback_query.inline_message_id, caption=text, reply_markup=keyboard, parse_mode="HTML")
                except Exception:
                    await bot.edit_message_text(inline_message_id=callback_query.inline_message_id, text=text, reply_markup=keyboard, parse_mode="HTML")
        except Exception as e:
             logger.error(f"Failed to edit message in show_country_selection: {e}")
             if message:
                 await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        if message:
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


# Service selection -> Show Countries
@dp.callback_query_handler(lambda c: c.data.startswith('select_service='), state="*")
async def process_service_selection(callback_query: types.CallbackQuery, state: FSMContext):
    # Finish any previous state
    current_state = await state.get_state()
    if current_state:
        await state.finish()
    
    # Исправляем парсинг: берем все после 'select_service='
    full_data = callback_query.data[len('select_service='):]
    
    if '|' in full_data:
        service = full_data.split('|')[0]
    else:
        service = full_data
        
    service = service.strip()
    logger.info(f"Service selected: '{service}'")

    # Отвечаем на callback сразу, чтобы убрать "часики"
    try:
        await callback_query.answer()
    except:
        pass

    # Передаем правильное название для отображения (Kleinanzeigen вместо ebay)
    # Но для API останется 'ebay', так как мы передаем 'service' в show_country_selection,
    # а она использует его для запросов.
    # Поэтому, мы добавим display_name в функцию show_country_selection
    
    display_name = service.capitalize()
    if service == 'ebay':
        display_name = 'Kleinanzeigen'
        
    await show_country_selection(callback_query, service, display_name=display_name)


@dp.callback_query_handler(text="search_service", state="*")
async def search_service_start(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Start service search flow
    """
    await BotStates.search_service.set()
    await callback_query.message.delete()
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Отмена", callback_data="activation_menu"))
    
    text = (
        "***🔎 Введите название сервиса (на английском):***\n"
        "***━━━━━━━━━━━***\n"
        "***⚠️ Укажите сервис, номер для которого требуется.***\n"
        "***━━━━━━━━━━━***\n"
        "***ℹ️ Пример: Vinted***"
    )
    
    await callback_query.message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


@dp.message_handler(state=BotStates.search_service)
async def process_search_service(message: types.Message, state: FSMContext):
    """
    Handle search input
    """
    service_name = message.text.lower().strip()
    await message.delete()
    
    # Basic validation
    if not service_name.replace('_', '').isalnum():
        await message.answer("***❌ Некорректное название. Используйте только латинские буквы.***\n***🔁 Попробуйте еще раз или нажмите Отмена.***", 
                             reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("Отмена", callback_data="activation_menu")), parse_mode="Markdown")
        return

    await message.answer(f"***🔎 Ищу сервис '{service_name}'...***", parse_mode="Markdown")
    
    # Try to find the service by requesting prices
    # If successful, it will show country selection
    await show_country_selection(message, service_name, page=0, edit_message=False)
    await state.finish()


# Country selection -> Show Operators/Prices
@dp.callback_query_handler(lambda c: c.data.startswith('select_country='))
async def process_country_selection(callback_query: types.CallbackQuery):
    _, data = callback_query.data.split('=')
    service, country = data.split('|')
    
    # Не используем await callback_query.answer(), так как это блокирующий вызов
    # и при плохом соединении он может вызвать NetworkError, прерывая всю функцию.
    # Вместо этого сразу редактируем сообщение или отправляем новое.
    try:
        await callback_query.answer("Загружаю цены...", cache_time=1)
    except Exception:
        # Игнорируем ошибку ответа на callback (например, если таймаут)
        pass
    
    # Fetch prices from 5sim
    logger.info(f"Requesting prices for {service}|{country}")
    prices_data = await FiveSimAPI.get_prices(country=country, product=service)
    logger.info(f"Prices received: {bool(prices_data)}")
    
    # Response structure:
    # { "telegram": { "megafon": { "cost": 10, "count": 100 }, ... } }
    
    if not prices_data or service not in prices_data:
        await callback_query.answer("Нет доступных номеров для этого сервиса в данной стране.", show_alert=True)
        return

    operators_data = prices_data[service]
    
    # Sort operators:
    # 1. By rate (descending) - Лучшие операторы сверху
    # 2. By cost (ascending) - Дешевые тоже хорошо
    # 3. By count (descending) - Где больше номеров
    sorted_operators = sorted(
        operators_data.items(), 
        key=lambda item: (
            -float(item[1].get('rate', 0) or 0), # Сначала высокий рейтинг (rate=None -> 0)
            float(item[1].get('cost', float('inf'))), # Потом низкая цена
            -int(item[1].get('count', 0)) # Потом количество
        )
    )
    
    found_any = False
    
    from src.config import MARGIN_PERCENT, CRYPTOBOT_COMMISSION
    from bin.pricing import calculate_dynamic_markup
    import math

    # Ищем минимальную цену среди всех операторов
    min_cost_usd = float('inf')
    
    for _, info in sorted_operators:
        try:
            c = float(info.get('cost', float('inf')))
            if c < min_cost_usd:
                min_cost_usd = c
        except:
            continue
            
    # Если нашли цену, рассчитываем наценку
    any_op_text = "🎲 Любой оператор (Авто)"
    any_op_price_usd = 0
    
    if min_cost_usd != float('inf'):
        # Цена 5sim (USD) + Наценка + Комиссия CryptoBot
        # 1. Добавляем нашу наценку (MARGIN_PERCENT)
        price_with_margin = calculate_dynamic_markup(min_cost_usd) # calculate_dynamic_markup теперь должна работать с USD
        
        # 2. Добавляем комиссию CryptoBot (3%)
        # Чтобы получить чистыми price_with_margin, пользователь должен заплатить X:
        # X * (1 - 0.03) = price_with_margin  => X = price_with_margin / 0.97
        final_usd = price_with_margin / (1 - CRYPTOBOT_COMMISSION)
        
        # Округляем до 2 знаков в большую сторону (было 4)
        final_usd = math.ceil(final_usd * 100) / 100
        
        any_op_price_usd = final_usd
        
        # 🎲 Любой оператор ┃ от $0.31
        any_op_text = f"🎲 Любой оператор ┃ от ${final_usd:.2f}"
    
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    # Кнопка "Любой оператор"
    keyboard.add(types.InlineKeyboardButton(
        text=any_op_text, 
        callback_data=f"buy_num={service}|{country}|any|{any_op_price_usd}"
    ))
    # Находим оператора с максимальным рейтингом (даже если он маленький) и даем ему ⭐️
    max_rate = -1
    best_operator_idx = -1
    
    # Проверяем, есть ли хоть один "хороший" оператор
    has_good_operators = any(
        (float(info.get('rate', 0) or 0) >= 20) 
        for _, info in sorted_operators
    )
    
    if not has_good_operators and sorted_operators:
        # Если хороших нет, ищем "лучшего из худших"
        for i, (_, info) in enumerate(sorted_operators):
            rate_val = float(info.get('rate', 0) or 0)
            if rate_val > max_rate:
                max_rate = rate_val
                best_operator_idx = i
    
    for idx, (operator, info) in enumerate(sorted_operators, 1):
        cost = info.get('cost')
        count = info.get('count')
        rate = info.get('rate', 0) # Процент успешных активаций
        
        if count and count > 0:
            found_any = True
            
            # ... расчет цен ...
            # 5sim API возвращает цену в USD (для этого аккаунта).
            base_cost_usd = float(cost)
            
            # 1. Наценка
            price_with_margin = calculate_dynamic_markup(base_cost_usd)
            
            # 2. Комиссия CryptoBot
            final_cost_usd = price_with_margin / (1 - CRYPTOBOT_COMMISSION)
            # Округляем до 2 знаков в большую сторону
            final_cost_usd = math.ceil(final_cost_usd * 100) / 100
            
            # Формирование текста кнопки с "умным" отображением рейтинга
            rate_display = ""
            try:
                rate_val = float(rate or 0)
                if rate_val >= 50:
                    rate_display = "┃ ⚡️"
                elif rate_val >= 20:
                    rate_display = "┃ ⭐️"
                else:
                    # Если это "лучший из худших" и нет реально хороших - даем ему звезду
                    if not has_good_operators and (idx - 1) == best_operator_idx:
                        rate_display = "┃ ⭐️"
                    else:
                        rate_display = "" 
            except ValueError:
                rate_display = ""

            # Генерируем красивое имя провайдера
            # Если в имени есть цифры (virtual51), используем их -> Провайдер #51
            # Если нет (megafon), генерируем хэш -> Провайдер #XX
            import re
            digits = re.findall(r'\d+', operator)
            if digits:
                display_id = digits[-1] # Берем последние цифры
            else:
                import hashlib
                hash_val = int(hashlib.md5(operator.encode()).hexdigest(), 16)
                display_id = (hash_val % 99) + 1

            # Провайдер #51 ┃ $0.31 ┃ ⚡️
            btn_text = f"Провайдер #{display_id} ┃ ${final_cost_usd:.2f} {rate_display}"
            
            keyboard.add(types.InlineKeyboardButton(
                text=btn_text, 
                callback_data=f"buy_num={service}|{country}|{operator}|{final_cost_usd}"
            ))
            
    keyboard.add(types.InlineKeyboardButton(text="Назад", callback_data=f"select_service={service}"))
    
    # Получаем красивое название страны с флагом
    from bin.country_utils import get_country_info
    info = get_country_info(country)
    country_display = f"{info['flag']} {info['name']}" if info else country.title()

    # Custom Emojis IDs
    # Service: 5260348422266822411 (💬)
    # Country: 5258509201306557640 (📍)
    # Operator: 5893161718179173515 (📶)
    
    s_emoji = '<tg-emoji emoji-id="5260348422266822411">💬</tg-emoji>'
    c_emoji = '<tg-emoji emoji-id="5258509201306557640">📍</tg-emoji>'
    o_emoji = '<tg-emoji emoji-id="5893161718179173515">📶</tg-emoji>'

    text = f"{s_emoji} <b>Сервис: {service.capitalize()}</b>\n" \
           f"{c_emoji} <b>Страна: {country_display}</b>\n" \
           f"{o_emoji} <b>Выберите оператора:</b>"
    
    # Если мы нашли хоть одного оператора, отлично. Если нет - кнопка "Любой" все равно останется.
    # Но стоит предупредить пользователя
    if not found_any:
        text += "\n\n<b>⚠️ Конкретные операторы недоступны, попробуйте 'Любой оператор'</b>"
    
    try:
        if callback_query.message:
            try:
                await callback_query.message.edit_caption(caption=text, reply_markup=keyboard, parse_mode="HTML")
            except Exception:
                await callback_query.message.edit_text(text=text, reply_markup=keyboard, parse_mode="HTML")
        elif callback_query.inline_message_id:
            try:
                await bot.edit_message_caption(inline_message_id=callback_query.inline_message_id, caption=text, reply_markup=keyboard, parse_mode="HTML")
            except Exception:
                await bot.edit_message_text(inline_message_id=callback_query.inline_message_id, text=text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to edit message in process_country_selection: {e}")
        # Last resort: send new message if possible
        if callback_query.message:
            await callback_query.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

# Buy number confirmation/action
@dp.callback_query_handler(lambda c: c.data.startswith('buy_num='))
async def process_buy_number(callback_query: types.CallbackQuery):
    _, data = callback_query.data.split('=')
    service, country, operator, price = data.split('|')
    
    user_id = callback_query.from_user.id
    
    # ПРИНУДИТЕЛЬНОЕ ОБНОВЛЕНИЕ ЦЕНЫ ПЕРЕД ПОДТВЕРЖДЕНИЕМ
    logger.info(f"Price update before confirmation: {service}|{country}|{operator}")
    new_price = await get_updated_price(service, country, operator)
    
    if new_price:
        logger.info(f"Price updated: {price} -> {new_price}")
        price = str(new_price)
        # Обновляем data для confirm_buy
        data = f"{service}|{country}|{operator}|{price}"
    else:
        logger.warning(f"Failed to update price for {service}|{country}|{operator}. Using old price: {price}")

    # Check balance
    current_balance = await database.get_user_balance(user_id)
    
    price_val_usd = float(price)
    price_display = f"${price_val_usd:.2f}"
    
    if current_balance < price_val_usd:
        await callback_query.answer(f"Недостаточно средств! Актуальная цена: ${price_val_usd:.2f}\nВаш баланс: ${current_balance:.2f}", show_alert=True)
        return
    
    # Confirm buy
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="Купить", callback_data=f"confirm_buy={data}"))
    keyboard.add(types.InlineKeyboardButton(text="Отмена", callback_data=f"select_country={service}|{country}"))
    
    # Красивое название страны
    from bin.country_utils import get_country_info
    info = get_country_info(country)
    country_display = f"{info['flag']} {info['name']}" if info else country.title()
    
    # Находим индекс оператора для отображения "Провайдер #X"
    provider_display = operator
    
    if operator == 'any':
        provider_display = "🎲 Любой оператор (Авто)"
    else:
        # Smart Naming Logic (дублируем логику для согласованности)
        import re
        digits = re.findall(r'\d+', operator)
        if digits:
            display_id = digits[-1]
        else:
            import hashlib
            hash_val = int(hashlib.md5(operator.encode()).hexdigest(), 16)
            display_id = (hash_val % 99) + 1
            
        provider_display = f"Провайдер #{display_id}"

    # Calculate balance in USD
    balance_usd = current_balance

    # Premium Emojis
    e_cart = '<tg-emoji emoji-id="5902056028513505203">🛒</tg-emoji>'
    e_service = '<tg-emoji emoji-id="5260348422266822411">📱</tg-emoji>'
    e_country = '<tg-emoji emoji-id="5258509201306557640">🌍</tg-emoji>'
    e_operator = '<tg-emoji emoji-id="5893161718179173515">📶</tg-emoji>'
    e_price = '<tg-emoji emoji-id="5902056028513505203">💰</tg-emoji>'
    e_balance = '<tg-emoji emoji-id="5258204546391351475">💳</tg-emoji>'

    text = f"{e_cart} <b>Подтверждение покупки</b>\n" \
           f"<b>━━━━━━━━━━━</b>\n" \
           f"{e_service} <b>Сервис: {service.capitalize()}</b>\n" \
           f"{e_country} <b>Страна: {country_display}</b>\n" \
           f"{e_operator} <b>Оператор: {provider_display}</b>\n" \
           f"<b>━━━━━━━━━━━</b>\n" \
           f"{e_price} <b>Цена: {price_display}</b>\n" \
           f"{e_balance} <b>Ваш баланс: ${balance_usd:.2f}</b>"
           
    try:
        if callback_query.message:
            try:
                await callback_query.message.edit_caption(caption=text, reply_markup=keyboard, parse_mode="HTML")
            except:
                await callback_query.message.edit_text(text=text, reply_markup=keyboard, parse_mode="HTML")
        elif callback_query.inline_message_id:
            try:
                await bot.edit_message_caption(inline_message_id=callback_query.inline_message_id, caption=text, reply_markup=keyboard, parse_mode="HTML")
            except:
                await bot.edit_message_text(inline_message_id=callback_query.inline_message_id, text=text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
         logger.error(f"Failed to edit message in process_buy_number: {e}")

@dp.callback_query_handler(lambda c: c.data.startswith('confirm_buy='))
async def process_confirm_buy(callback_query: types.CallbackQuery):
    _, data = callback_query.data.split('=')
    service, country, operator, price = data.split('|')
    
    user_id = callback_query.from_user.id
    current_balance = await database.get_user_balance(user_id)
    
    # ПРИНУДИТЕЛЬНОЕ ОБНОВЛЕНИЕ ЦЕНЫ ПРЯМО ПЕРЕД ПОКУПКОЙ (Last Mile Check)
    logger.info(f"Final price check before purchase for user {user_id}: {service}|{country}|{operator}")
    latest_price = await get_updated_price(service, country, operator)
    
    if latest_price and abs(latest_price - float(price)) > 0.001:
        logger.warning(f"Price changed: {price} -> {latest_price}")
        
        # Логируем изменение цены
        try:
            username_log = callback_query.from_user.username if callback_query.from_user.username else "no_username"
            await database.add_action_log(
                user_id=user_id,
                username=username_log,
                action_type="price_change",
                details=f"Цена изменилась: ${price} -> ${latest_price} (Сервис: {service}, Страна: {country})"
            )
        except Exception as e:
            logger.error(f"Failed to log price change: {e}")

        # Обновляем интерфейс с новой ценой
        price = str(latest_price)
        
        # Подготавливаем обновленную клавиатуру
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(text="Купить", callback_data=f"confirm_buy={service}|{country}|{operator}|{price}"))
        keyboard.add(types.InlineKeyboardButton(text="Отмена", callback_data=f"select_country={service}|{country}"))
        
        # Красивое название страны и оператора
        from bin.country_utils import get_country_info
        info = get_country_info(country)
        country_display = f"{info['flag']} {info['name']}" if info else country.title()
        
        provider_display = operator
        if operator == 'any':
            provider_display = "🎲 Любой оператор (Авто)"
        else:
            import re
            digits = re.findall(r'\d+', operator)
            display_id = digits[-1] if digits else "1"
            provider_display = f"Провайдер #{display_id}"

        # Premium Emojis (используем только те, что уже есть в коде)
        e_cart = '<tg-emoji emoji-id="5902056028513505203">🛒</tg-emoji>'
        e_service = '<tg-emoji emoji-id="5260348422266822411">📱</tg-emoji>'
        e_country = '<tg-emoji emoji-id="5258509201306557640">🌍</tg-emoji>'
        e_operator = '<tg-emoji emoji-id="5893161718179173515">📶</tg-emoji>'
        e_price = '<tg-emoji emoji-id="5902056028513505203">💰</tg-emoji>'
        e_balance = '<tg-emoji emoji-id="5258204546391351475">💳</tg-emoji>'
        e_warning = '⚠️'

        text = f"{e_warning} <b>Внимание: Цена изменилась!</b>\n" \
               f"<b>━━━━━━━━━━━</b>\n" \
               f"{e_service} <b>Сервис: {service.capitalize()}</b>\n" \
               f"{e_country} <b>Страна: {country_display}</b>\n" \
               f"{e_operator} <b>Оператор: {provider_display}</b>\n" \
               f"<b>━━━━━━━━━━━</b>\n" \
               f"{e_price} <b>Новая цена: ${latest_price:.2f}</b>\n" \
               f"{e_balance} <b>Ваш баланс: ${current_balance:.2f}</b>"
        
        if current_balance < latest_price:
            text += f"\n\n<b>❌ Недостаточно средств для покупки по новой цене!</b>"
            # Убираем кнопку покупки, если денег нет
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(text="Назад", callback_data=f"select_country={service}|{country}"))

        try:
            await callback_query.message.edit_caption(caption=text, reply_markup=keyboard, parse_mode="HTML")
        except:
            await callback_query.message.edit_text(text=text, reply_markup=keyboard, parse_mode="HTML")
            
        await callback_query.answer("Цена обновилась", show_alert=False)
        return
    
    if current_balance < float(price):
        await callback_query.answer("Недостаточно средств!", show_alert=True)
        return
    
    # Не отвечаем сразу, чтобы можно было показать alert в случае ошибки
    # await callback_query.answer("Покупаем номер...", cache_time=1)
    
    # 1. Покупаем номер в 5sim (деньги пока НЕ списываем с юзера)
    order = await FiveSimAPI.buy_number(country, operator, service)
    
    if not order or 'id' not in order:
         logger.warning(f"Failed to buy number. Order response: {order}")
         
         # Если покупка не удалась, возможно изменилась цена и она стала выше баланса юзера
         # или просто нет номеров. Но в 5sim покупка происходит по текущей цене API.
         
         # Check for specific errors
         if isinstance(order, dict) and order.get('error') == 'no_free_phones':
             # Используем show_alert=True для гарантированного уведомления пользователя,
             # так как в inline-режиме отправка сообщения в чат может не сработать.
             await callback_query.answer("⚠️ Нет свободных номеров у этого оператора.\nПопробуйте выбрать другого или 'Любой оператор'.", show_alert=True)
             
             # Опционально: попробуем отправить сообщение, если это не инлайн, но не падаем при ошибке
             try:
                 if callback_query.message:
                    await callback_query.message.answer("***⚠️ Нет свободных номеров у этого оператора.***\n***Попробуйте выбрать другого или 'Любой оператор'.***", parse_mode="Markdown")
             except Exception:
                 pass
         else:
             await callback_query.answer("Ошибка покупки. Попробуйте позже.", show_alert=True)
         return
    
    # 2. Номер куплен успешно -> Списываем деньги
    # Получаем реальную цену покупки из ответа (себестоимость в USD)
    real_cost_usd = float(order.get('price', 0))
    
    from src.config import MARGIN_PERCENT, CRYPTOBOT_COMMISSION
    from bin.pricing import calculate_dynamic_markup
    import math
    
    # 1. Наценка
    price_with_margin = calculate_dynamic_markup(real_cost_usd)
    
    # 2. Комиссия CryptoBot
    final_cost_usd = price_with_margin / (1 - CRYPTOBOT_COMMISSION)
    final_cost_usd = math.ceil(final_cost_usd * 100) / 100
    
    new_balance = current_balance - final_cost_usd
    
    # Защита от ухода в минус (хотя мы проверяли выше, но цена могла быть динамической)
    if new_balance < 0:
        logger.error(f"User {user_id} balance negative after purchase! Old: {current_balance}, Cost: {final_cost_usd}")
        # Отменяем заказ
        await FiveSimAPI.cancel_order(order['id'])
        await callback_query.answer("Ошибка: изменилась цена, недостаточно средств.", show_alert=True)
        return
    
    # Order successful
    order_id = order['id']
    phone = order['phone']

    await database.set_user_balance(user_id, new_balance)
    
    # Добавляем в логи (покупка номера)
    username_log = callback_query.from_user.username if callback_query.from_user.username else "no_username"
    await database.add_action_log(
        user_id=user_id,
        username=username_log,
        action_type="purchase",
        details=f"Покупка номера: {phone} (Сервис: {service}, Страна: {country}) на сумму ${final_cost_usd:.2f}"
    )
    
    # Show order info and start checking
    keyboard = types.InlineKeyboardMarkup()
    # Убираем кнопки "Проверить СМС" и "Завершить"
    # keyboard.add(types.InlineKeyboardButton(text="🔄 Проверить СМС", callback_data=f"check_sms={order_id}"))
    keyboard.add(types.InlineKeyboardButton(text="Отменить", callback_data=f"cancel_order={order_id}"))
    # keyboard.add(types.InlineKeyboardButton(text="✅ Завершить", callback_data=f"finish_order={order_id}"))
    
    # Custom Emojis
    # Success: 5895266423952904371 (✅)
    # ID: 5902453596456227896 (🆔)
    # Phone: 5258337316715373336 (🤙/📱)
    # Wait: 5893102202817352158 (⏳)
    
    e_success = '<tg-emoji emoji-id="5895266423952904371">✅</tg-emoji>'
    e_id = '<tg-emoji emoji-id="5902453596456227896">🆔</tg-emoji>'
    e_phone = '<tg-emoji emoji-id="5258337316715373336">📱</tg-emoji>'
    e_wait = '<tg-emoji emoji-id="5893102202817352158">⏳</tg-emoji>'
    
    # Логика определения номера без кода страны (через phonenumbers)
    phone_no_code = phone
    try:
        import phonenumbers
        
        # 5sim обычно возвращает номер с +, но на всякий случай нормализуем
        phone_to_parse = phone
        if not phone_to_parse.startswith('+'):
            phone_to_parse = '+' + phone_to_parse
            
        # Пытаемся распарсить. Библиотека сама определит страну по коду.
        parsed_num = phonenumbers.parse(phone_to_parse, None)
        
        # Получаем "Национальный значащий номер" (без кода страны)
        phone_no_code = phonenumbers.national_significant_number(parsed_num)
        
    except ImportError:
        logger.error("phonenumbers library not installed")
        # Fallback to old logic
        from bin.country_utils import get_country_info
        c_info = get_country_info(country)
        if c_info and 'prefix' in c_info:
             prefix = str(c_info['prefix'])
             clean_phone = phone.lstrip('+')
             if clean_phone.startswith(prefix):
                 phone_no_code = clean_phone[len(prefix):]
                 
    except Exception as e:
        logger.error(f"Error parsing phone number {phone}: {e}")
        # Fallback
        pass

    text = f"{e_success} <b>Номер получен!</b>\n" \
           f"<b>━━━━━━━━━━━</b>\n" \
           f"{e_id} <b>ID: {order_id}</b>\n" \
           f"{e_phone} <b>Номер: <code>{phone}</code></b>\n" \
           f"<b>└ Без кода страны: <code>{phone_no_code}</code></b>\n" \
           f"<b>━━━━━━━━━━━</b>\n" \
           f"{e_wait} <b>Ждём СМС...</b>"
           
    try:
        sent_msg = None
        if callback_query.message:
            try:
                sent_msg = await callback_query.message.edit_caption(caption=text, reply_markup=keyboard, parse_mode="HTML")
            except:
                sent_msg = await callback_query.message.edit_text(text=text, reply_markup=keyboard, parse_mode="HTML")
        elif callback_query.inline_message_id:
             try:
                await bot.edit_message_caption(inline_message_id=callback_query.inline_message_id, caption=text, reply_markup=keyboard, parse_mode="HTML")
             except:
                await bot.edit_message_text(inline_message_id=callback_query.inline_message_id, text=text, reply_markup=keyboard, parse_mode="HTML")
        
        # ДОБАВЛЯЕМ ЗАКАЗ В БД ДЛЯ ЧЕКЕРА
        msg_id = sent_msg.message_id if sent_msg else None
        chat_id = sent_msg.chat.id if sent_msg else None
        if not msg_id and callback_query.message:
            msg_id = callback_query.message.message_id
            chat_id = callback_query.message.chat.id
            
        await database.add_order(
            user_id=user_id,
            order_id=order_id,
            service=service,
            country=country,
            operator=operator,
            phone=phone,
            price=final_cost_usd,
            message_id=msg_id,
            chat_id=chat_id
        )
        
    except Exception as e:
         logger.error(f"Failed to edit message in process_confirm_buy: {e}")

@dp.callback_query_handler(lambda c: c.data.startswith('check_sms='))
async def process_check_sms(callback_query: types.CallbackQuery):
    order_id = callback_query.data.split('=')[1]
    
    order = await FiveSimAPI.check_order(order_id)
    
    if not order:
        await callback_query.answer("Ошибка проверки.", show_alert=True)
        return
        
    status = order.get('status')
    sms_list = order.get('sms', [])
    
    if sms_list:
        # SMS received!
        code = sms_list[0].get('code')
        text = sms_list[0].get('text')
        
        # ИЗМЕНЕНИЕ: Записываем в историю покупок СЕЙЧАС (когда пришло СМС)
        # Нам нужно проверить, не записали ли мы уже этот заказ (чтобы не дублировать при повторном нажатии "Проверить СМС")
        
        # Проверяем наличие в БД
        existing_sale = False
        # Тут нам пригодилась бы функция проверки, но мы можем просто попробовать добавить,
        # или проверить get_user_buy и поискать там этот чек.
        # Или проще: add_buy возвращает ID. Если мы сделаем проверку внутри add_buy или перед ней.
        # В database.py add_buy просто добавляет.
        
        # Сделаем проверку через чек
        from sqlalchemy import select
        from src.database_models import Sale
        from database import async_session
        
        is_recorded = False
        async with async_session() as session:
             res = await session.execute(select(Sale).where(Sale.cheque == str(order_id)))
             if res.scalar_one_or_none():
                 is_recorded = True
        
        if not is_recorded:
            from bin.strings import get_now_date
            from bin.country_utils import get_country_info
            from bin.pricing import calculate_dynamic_markup
            from src.config import CRYPTOBOT_COMMISSION
            import math
            
            # Нам нужны данные о сервисе и стране и ЦЕНЕ.
            # В order_info есть 'country', 'product', 'price'
            c_code = order.get('country')
            s_name = order.get('product')
            real_cost_usd = float(order.get('price', 0))
            
            # Рассчитываем цену, которую заплатил юзер
            price_with_margin = calculate_dynamic_markup(real_cost_usd)
            final_cost_usd = price_with_margin / (1 - CRYPTOBOT_COMMISSION)
            final_cost_usd = math.ceil(final_cost_usd * 100) / 100
            
            info = get_country_info(c_code)
            country_name = info['name'] if info else c_code.title()
            
            purchase_data = {
                'user_id': callback_query.from_user.id,
                'item_name': f"{s_name.capitalize()} ({country_name})",
                'amount': final_cost_usd,
                'count': 1,
                'date': get_now_date(),
                'cheque': str(order_id)
            }
            await database.add_buy(purchase_data)
            logger.info(f"Order {order_id} recorded in history (SMS received)")

        # Custom Emojis for SMS
        # Success SMS: 5895713431264170680
        # Phone: 5258337316715373336
        # Code: 5429571366384842791
        # Text: 5257965174979042426
        
        e_sms_success = '<tg-emoji emoji-id="5895713431264170680">✅</tg-emoji>'
        e_phone = '<tg-emoji emoji-id="5258337316715373336">📱</tg-emoji>'
        e_code = '<tg-emoji emoji-id="5429571366384842791">🔢</tg-emoji>'
        e_text = '<tg-emoji emoji-id="5257965174979042426">📩</tg-emoji>'

        # В тексте СМС нам нужно найти код и сделать его моноширинным, если он там есть.
        # Но пользователь просит "код в текст: тоже моноспейс копируемый при клике".
        # Если мы просто сделаем весь текст СМС обычным, а код внутри него моноширинным?
        # Или имеется в виду, что весь текст сообщения от сервиса.
        # Судя по запросу: "Текст: Su codigo ... 238107" -> код внутри текста тоже должен быть `code`.
        # Попробуем заменить найденный код в тексте на `code`.
        
        text_formatted = text
        if code and code in text_formatted:
            text_formatted = text_formatted.replace(code, f"<code>{code}</code>")

        msg_text = f"{e_sms_success} <b>СМС ПРИШЛО!</b>\n" \
                   f"<b>━━━━━━━━━━━</b>\n" \
                   f"{e_phone} <b>Номер: <code>{order.get('phone')}</code></b>\n" \
                   f"{e_code} <b>Код: <code>{code}</code></b>\n" \
                   f"<b>━━━━━━━━━━━</b>\n" \
                   f"{e_text} <b>Текст: {text_formatted}</b>"
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(text="✅ Завершить", callback_data=f"finish_order={order_id}"))
        
        try:
            if callback_query.message:
                try:
                    await callback_query.message.edit_caption(caption=msg_text, reply_markup=keyboard, parse_mode="HTML")
                except:
                    await callback_query.message.edit_text(text=msg_text, reply_markup=keyboard, parse_mode="HTML")
            elif callback_query.inline_message_id:
                try:
                    await bot.edit_message_caption(inline_message_id=callback_query.inline_message_id, caption=msg_text, reply_markup=keyboard, parse_mode="HTML")
                except:
                    await bot.edit_message_text(inline_message_id=callback_query.inline_message_id, text=msg_text, reply_markup=keyboard, parse_mode="HTML")
        except Exception as e:
             logger.error(f"Failed to edit message in process_check_sms: {e}")
            
    else:
        await callback_query.answer(f"Статус: {status}. СМС пока нет.", show_alert=True)

@dp.callback_query_handler(lambda c: c.data.startswith('cancel_order='))
async def process_cancel_order(callback_query: types.CallbackQuery):
    order_id = callback_query.data.split('=')[1]
    
    # ПРОВЕРКА ВРЕМЕНИ (1.5 МИНУТЫ)
    # Нам нужно узнать время создания заказа. 
    # Так как мы теперь сохраняем заказы в БД, можем взять оттуда.
    # Если заказа нет в БД (старый заказ до обновления), разрешаем отмену (или запрещаем, но лучше разрешить для совместимости)
    
    order = await database.get_order(order_id)
    if order:
        import time
        now = time.time()
        # 1.5 минуты = 90 секунд
        if now - order.created_at < 90:
            remaining = int(90 - (now - order.created_at))
            await callback_query.answer(f"⚠️ Отмена доступна через {remaining} сек.", show_alert=True)
            return
            
    # ... (далее старый код)
    
    # БЛОКИРОВКА ПОВТОРНЫХ НАЖАТИЙ (Race Condition Fix)
    if order_id in processing_cancellations:
        logger.warning(f"Order {order_id} is already being cancelled. Ignoring duplicate request.")
        try:
            await callback_query.answer("⚠️ Уже обрабатывается...", show_alert=True)
        except:
            pass
        return

    if order_id in refunded_orders:
        await callback_query.answer("⚠️ Уже отменено и возвращено.", show_alert=True)
        try:
            if callback_query.message:
                await callback_query.message.edit_reply_markup(reply_markup=types.InlineKeyboardMarkup())
            elif callback_query.inline_message_id:
                await bot.edit_message_reply_markup(inline_message_id=callback_query.inline_message_id, reply_markup=types.InlineKeyboardMarkup())
        except:
             pass
        return

    processing_cancellations.add(order_id)
    
    try:
        # Лучший способ без БД - это проверить статус в 5sim.
        # Если 5sim говорит, что заказ уже отменен (Canceled/Finished) -> НЕ возвращаем деньги повторно.
        
        try:
            await callback_query.answer("Отменяем...", cache_time=1)
        except:
            pass

        # Получаем актуальный статус заказа из 5sim
        order_info = await FiveSimAPI.check_order(order_id)
        
        if not order_info:
            await callback_query.message.answer("❌ Заказ не найден или уже удален.", parse_mode="Markdown")
            return

        status = order_info.get('status')
        sms_list = order_info.get('sms', [])
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ (Race Condition Fix):
        # Проверяем наличие СМС. Если СМС есть (список не пуст), значит услуга оказана.
        # В этом случае ОТМЕНЯТЬ НЕЛЬЗЯ, даже если статус еще не FINISHED.
        if sms_list or status == 'FINISHED' or status == 'BANNED':
             await callback_query.answer("❌ СМС уже получено! Отмена невозможна.", show_alert=True)
             
             # Пытаемся обновить сообщение, чтобы показать СМС, если оно еще не показано
             # (но обычно чекер это делает быстрее)
             return

        # ЕСЛИ ЗАКАЗ УЖЕ ОТМЕНЕН (CANCELED) ИЛИ ЗАВЕРШЕН (FINISHED)
        # ЗНАЧИТ МЫ ЕГО УЖЕ ОБРАБОТАЛИ ИЛИ 5SIM ЕГО ЗАКРЫЛ.
        
        # Сразу меняем кнопки, чтобы юзер не мог нажать еще раз (визуальная защита)
        try:
            if callback_query.message:
                await callback_query.message.edit_reply_markup(reply_markup=types.InlineKeyboardMarkup()) # Убираем кнопки
            elif callback_query.inline_message_id:
                await bot.edit_message_reply_markup(inline_message_id=callback_query.inline_message_id, reply_markup=types.InlineKeyboardMarkup())
        except Exception as e:
            logger.warning(f"Could not remove buttons: {e}")
        
        # Если статус уже 'FINISHED' или 'BANNED' (код получен) -> нельзя отменять
        # (Эта проверка теперь дублирует верхнюю, но оставим для надежности)
        if status == 'FINISHED' or status == 'BANNED' or order_info.get('sms'):
             await callback_query.message.answer("❌ Нельзя отменить завершенный заказ.", parse_mode="Markdown")
             return

        # Если статус уже CANCELED, значит он уже отменен.
        # Мы должны убедиться, что не возвращаем деньги дважды.
        # Поскольку у нас нет БД транзакций, мы полагаемся на то, что processing_cancellations
        # не даст зайти сюда дважды одновременно.
        # А если статус CANCELED был до нас (например, таймаут)? 
        # Тогда мы должны вернуть деньги, если еще не возвращали. 
        # Но мы не знаем, возвращали ли.
        # ПРЕДПОЛОЖЕНИЕ: Если юзер нажал отмену, и мы тут, значит мы инициируем возврат.
        
        # Пробуем отменить в 5sim
        cancel_result = await FiveSimAPI.cancel_order(order_id)
        
        if not cancel_result or 'error' in cancel_result:
             # Если не удалось отменить (например, пришло СМС в последний момент)
             # Проверяем статус еще раз, чтобы сказать юзеру точную причину
             latest_info = await FiveSimAPI.check_order(order_id)
             
             # И ТУТ ТОЖЕ ПРОВЕРЯЕМ СМС
             if latest_info and (latest_info.get('status') == 'FINISHED' or latest_info.get('sms')):
                 await callback_query.message.answer("❌ Не удалось отменить заказ: получено СМС.", parse_mode="Markdown")
             else:
                 await callback_query.message.answer("❌ Ошибка при отмене заказа. Попробуйте позже.", parse_mode="Markdown")
             return

        # ВОЗВРАТ СРЕДСТВ
        # Только если отмена в 5sim прошла успешно
        
        # Сначала проверяем, не отменили ли мы его уже (Race Condition Fix 2)
        # Получаем актуальный статус из нашей БД
        current_order_db = await database.get_order(order_id)
        if current_order_db and current_order_db.status in ['CANCELLED', 'EXPIRED', 'FINISHED']:
             await callback_query.answer("⚠️ Заказ уже обработан.", show_alert=True)
             return

        # Если все ок, делаем возврат
        user_id = callback_query.from_user.id
        current_balance = await database.get_user_balance(user_id)
        
        real_cost_usd = float(order_info.get('price', 0))
        from src.config import CRYPTOBOT_COMMISSION
        from bin.pricing import calculate_dynamic_markup
        import math
        
        # Расчет возврата (та же формула, что при покупке)
        price_with_margin = calculate_dynamic_markup(real_cost_usd)
        final_cost_usd = price_with_margin / (1 - CRYPTOBOT_COMMISSION)
        refund_amount = math.ceil(final_cost_usd * 100) / 100
        
        new_balance = current_balance + refund_amount
        await database.set_user_balance(user_id, new_balance)
        
        # Добавляем в логи (возврат)
        username_log = callback_query.from_user.username if callback_query.from_user.username else "no_username"
        await database.add_action_log(
            user_id=user_id,
            username=username_log,
            action_type="refund",
            details=f"Возврат за номер {order_info.get('phone', 'unknown')} на сумму ${refund_amount:.2f} (Отмена заказа)"
        )
        
        # ОБНОВЛЯЕМ СТАТУС В БД (Важно для чекера)
        await database.update_order_status(order_id, 'CANCELLED')
        
        # Удаляем запись о покупке из истории
        # ИЗМЕНЕНИЕ: Так как мы теперь пишем в историю только по факту СМС,
        # то при отмене заказа (когда СМС не пришло) удалять нечего.
        # await database.delete_buy_by_cheque(str(order_id))
        
        # Mark as refunded to prevent future duplicates
        refunded_orders.add(order_id)
        
        logger.info(f"Refunded ${refund_amount} to user {user_id} for order {order_id}")
        
        # Обновляем сообщение
        try:
            # Кнопка "Купить снова"
            # Для этого нам нужны параметры покупки. 
            # order_info уже содержит country, product, price. 
            # operator? 
            operator = order_info.get('operator', 'any') # Если оператора нет, используем 'any'
            
            # Нам нужно найти реальную цену (callback value), которую юзер видит на кнопке.
            # Но мы можем просто заново запустить процесс покупки через "Любой оператор" или тот же самый.
            # Если мы передадим 'any' в оператора, то цена будет динамической.
            
            # Лучше всего попробовать реконструировать callback для покупки.
            # buy_num={service}|{country}|{operator}|{price}
            
            service = order_info.get('product')
            country = order_info.get('country')
            
            # В order_info price - это то что мы заплатили 5sim (себестоимость).
            # Нам нужно передать цену продажи.
            # Мы можем пересчитать её.
            
            from bin.pricing import calculate_dynamic_markup
            from src.config import CRYPTOBOT_COMMISSION
            import math
            
            real_cost_usd = float(order_info.get('price', 0))
            price_with_margin = calculate_dynamic_markup(real_cost_usd)
            final_cost_usd = price_with_margin / (1 - CRYPTOBOT_COMMISSION)
            final_cost_usd = math.ceil(final_cost_usd * 100) / 100
            
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(
                text="Купить снова", 
                callback_data=f"buy_num={service}|{country}|{operator}|{final_cost_usd}"
            ))
            
            # Custom Emojis
            # Cancel: 5258318620722733379
            # Refund: 5902056028513505203
            
            e_cancel = '<tg-emoji emoji-id="5258318620722733379">✅</tg-emoji>'
            e_refund = '<tg-emoji emoji-id="5902056028513505203">💰</tg-emoji>'
            
            msg_text = f"{e_cancel} <b>Заказ отменен</b>\n" \
                       f"{e_refund} <b>Возвращено: <code>${refund_amount:.2f}</code></b>"
            
            if callback_query.message:
                msg_func = callback_query.message.edit_caption if callback_query.message.caption else callback_query.message.edit_text
                try:
                    await msg_func(text=msg_text, reply_markup=keyboard, parse_mode="HTML")
                except Exception:
                    await callback_query.message.answer(msg_text, reply_markup=keyboard, parse_mode="HTML")
            elif callback_query.inline_message_id:
                # Пытаемся редактировать caption, если не выйдет - text
                try:
                     await bot.edit_message_caption(inline_message_id=callback_query.inline_message_id, caption=msg_text, reply_markup=keyboard, parse_mode="HTML")
                except:
                     await bot.edit_message_text(inline_message_id=callback_query.inline_message_id, text=msg_text, reply_markup=keyboard, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to edit message in process_cancel_order: {e}")

    except Exception as e:
        logger.error(f"Error cancelling order {order_id}: {e}")
        try:
            await callback_query.answer("Ошибка отмены.", show_alert=True)
        except:
            pass
    finally:
        # Убираем из списка обработки через небольшую задержку или сразу?
        # Если убрать сразу, юзер может нажать снова, если кнопки не пропали.
        # Но кнопки мы убрали.
        # Оставляем в set навсегда? Нет, память потечет.
        # Удаляем. Если кнопки убраны, юзер не нажмет.
        if order_id in processing_cancellations:
            processing_cancellations.remove(order_id)

@dp.callback_query_handler(lambda c: c.data.startswith('finish_order='))
async def process_finish_order(callback_query: types.CallbackQuery):
    try:
        order_id = callback_query.data.split('=')[1]
        await FiveSimAPI.finish_order(order_id)
        try:
            await callback_query.answer("Заказ завершен", show_alert=True)
        except Exception:
            pass # Ignore if answer fails
            
        try:
            if callback_query.message:
                await callback_query.message.delete()
        except Exception as e:
            logger.error(f"Failed to delete message: {e}")
            # If delete fails, try to edit it to show it's finished
            try:
                if callback_query.message:
                    await callback_query.message.edit_caption(caption="***✅ Заказ завершен***", parse_mode="Markdown")
                elif callback_query.inline_message_id:
                     await bot.edit_message_caption(inline_message_id=callback_query.inline_message_id, caption="***✅ Заказ завершен***", parse_mode="Markdown")
            except:
                pass
    except Exception as e:
        logger.error(f"Error in finish_order: {e}")
        try:
            await callback_query.answer("Ошибка завершения заказа", show_alert=True)
        except:
            pass

@dp.callback_query_handler(text="activation_menu")
async def activation_menu(callback_query: types.CallbackQuery):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    # Row 1
    keyboard.row(
        types.InlineKeyboardButton(text="Telegram", callback_data="select_service=telegram"),
        types.InlineKeyboardButton(text="Whatsapp", callback_data="select_service=whatsapp")
    )
    # Row 2
    keyboard.row(
        types.InlineKeyboardButton(text="Wallapop", callback_data="select_service=wallapop"),
        types.InlineKeyboardButton(text="Marktplaats", callback_data="select_service=marktplaats")
    )
    # Row 3
    # В 5sim сервис называется 'ebay' или 'ebay-kleinanzeigen'. 
    # Если мы передаем 'kleinanzeigen', API возвращает 400 product is incorrect.
    # Поэтому на кнопке пишем "Kleinanzeigen", а в callback передаем "ebay".
    keyboard.row(
        types.InlineKeyboardButton(text="Subito", callback_data="select_service=subito"),
        types.InlineKeyboardButton(text="Kleinanzeigen", callback_data="select_service=ebay")
    )
 
    # Large buttons
    keyboard.add(types.InlineKeyboardButton(text="Любой другой", switch_inline_query_current_chat="country_for_other "))
    keyboard.add(types.InlineKeyboardButton(text="Поиск сервиса", switch_inline_query_current_chat=""))
    
    keyboard.add(types.InlineKeyboardButton(text="Назад", callback_data="open_shop"))
    
    caption_text = "<tg-emoji emoji-id=\"5260348422266822411\">💬</tg-emoji> <b>Выберите сервис для активации:</b>"
    
    try:
        await callback_query.message.edit_caption(caption=caption_text, reply_markup=keyboard, parse_mode="HTML")
    except:
        await callback_query.message.edit_text(text=caption_text, reply_markup=keyboard, parse_mode="HTML")

@dp.callback_query_handler(text="hosting_menu")
async def hosting_menu(callback_query: types.CallbackQuery):
    await callback_query.answer("Раздел Аренда в разработке", show_alert=True)

@dp.callback_query_handler(text="saints_team")
async def saints_team_callback(callback_query: types.CallbackQuery):
    await callback_query.answer("Saints Team - информация будет добавлена позже.", show_alert=True)

@dp.callback_query_handler(text="open_shop")
async def back_to_shop(callback_query: types.CallbackQuery):
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    keyboard.add(types.InlineKeyboardButton(text="Активация", callback_data="activation_menu"))
    keyboard.add(types.InlineKeyboardButton(text="Аренда", callback_data="hosting_menu"))
    keyboard.add(CLOSE_BTN)
    
    caption_text = "<b>Выберите тип услуги:</b>"
    
    try:
        await callback_query.message.edit_caption(caption=caption_text, reply_markup=keyboard, parse_mode="HTML")
    except:
        await callback_query.message.edit_text(text=caption_text, reply_markup=keyboard, parse_mode="HTML")
