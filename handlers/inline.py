from aiogram import types
from loader import dp
from bin.api_5sim import FiveSimAPI
import hashlib
import logging

logger = logging.getLogger(__name__)

@dp.inline_handler(lambda query: query.query.startswith('country '))
async def inline_country_search(inline_query: types.InlineQuery):
    query = inline_query.query.replace('country ', '').strip()
    # Разделяем по первому пробелу: "whatsapp германия" -> ["whatsapp", "германия"]
    # Если пробела нет: "whatsapp" -> ["whatsapp"]
    parts = query.split(' ', 1)
    
    if not parts or not parts[0]:
        return

    service = parts[0]
    search_term = parts[1].lower() if len(parts) > 1 else ""
    
    # Добавим логирование для отладки
    logger.info(f"Inline country search: service={service}, term='{search_term}'")
    
    # ВАЖНО: Если search_term пустой, показываем все страны (до 50 шт)
    # Если search_term есть, фильтруем
    
    try:
        # Для wallapop и других сервисов, где countries может быть пустым, если мы неправильно парсим
        # Добавим логирование результата
        countries = await FiveSimAPI.get_countries_for_service(service)
        logger.info(f"Loaded {len(countries)} countries for {service}")
    except Exception as e:
        logger.error(f"Error getting countries for {service}: {e}")
        return
    
    if not countries:
        logger.info(f"No countries found for {service}")
        # Можно отправить пустой ответ или сообщение об ошибке
        # await inline_query.answer([], cache_time=1, switch_pm_text="Стран не найдено", switch_pm_parameter="no_countries")
        return

    results = []
    count = 0
    
    # Сортировка: сначала популярные страны, если запрос пустой
    if not search_term:
        # Можно добавить приоритет для популярных стран, но пока оставим как есть (по алфавиту)
        pass
    
    for country_code, country_name in countries:
        # Логика фильтрации
        match = False
        if not search_term:
            match = True # Показываем все, если запрос пустой
        # Проверяем вхождение в русское название ИЛИ в английский код
        elif search_term in country_name.lower() or search_term in country_code.lower():
            match = True
        # Добавляем транслитерацию для поиска "ispaniya" -> "Испания" или "italy" -> "Италия"
        elif country_name.lower().startswith(search_term):
            match = True
            
        if match:
            flag = FiveSimAPI.get_country_flag(country_code)
            
            # Уникальный ID обязателен
            result_id = f"{service}_{country_code}_{count}"
            
            results.append(types.InlineQueryResultArticle(
                id=result_id,
                title=f"{flag} {country_name.title()}",
                description=f"Купить номер {service} ({country_name})",
                # Отправляем сообщение, которое триггерит callback на выбор страны
                input_message_content=types.InputTextMessageContent(
                    message_text=f"***⏳ Выбрана страна: {flag} {country_name}. Загрузка...***",
                    parse_mode="Markdown"
                ),
                reply_markup=types.InlineKeyboardMarkup().add(
                    types.InlineKeyboardButton("✅ Перейти к выбору", callback_data=f"select_country={service}|{country_code}")
                )
            ))
            count += 1
            if count >= 50: # Telegram limit
                break
                
    try:
        # cache_time=0 для мгновенного обновления при вводе
        # is_personal=False чтобы кэш был общим (хотя при cache_time=0 это не важно)
        logger.info(f"Sending {len(results)} results for {service} query='{search_term}'")
        await inline_query.answer(results, cache_time=0, is_personal=False)
    except Exception as e:
        logger.error(f"Error sending inline answer: {e}")

@dp.inline_handler(lambda query: True)
async def inline_search_service(query: types.InlineQuery):
    search_term = query.query.lower().strip()
    logger.info(f"Inline search query: '{search_term}' from user {query.from_user.id}")
    
    # Режим выбора страны для "Любой другой"
    if search_term.startswith("country_for_other"):
        country_query = search_term.replace("country_for_other", "").strip()
        from bin.country_utils import COUNTRY_DATA
        
        results = []
        count = 0
        
        # Сортируем страны (Европа -> Азия -> Остальные) для красивого отображения в поиске
        from bin.country_utils import get_country_sort_key
        sorted_codes = sorted(COUNTRY_DATA.keys(), key=get_country_sort_key)
        
        for code in sorted_codes:
            info = COUNTRY_DATA[code]
            name = info['name']
            flag = info['flag']
            full_name = f"{flag} {name}"
            
            if country_query in name.lower() or country_query in code.lower():
                result_id = hashlib.md5(f"other_{code}".encode()).hexdigest()
                results.append(
                    types.InlineQueryResultArticle(
                        id=result_id,
                        title=full_name,
                        input_message_content=types.InputTextMessageContent(
                            message_text=f"***🔍 Выбрана страна для Other: {name}|{code}***",
                            parse_mode="Markdown"
                        ),
                        description=f"Сервис: Any Other (Любой другой)"
                    )
                )
                count += 1
                if count >= 50: break
        
        try:
            await query.answer(results, cache_time=300, is_personal=False)
            logger.info(f"Sent country results for other: {len(results)}")
        except Exception as e:
            logger.error(f"Error sending inline country results: {e}")
        return

    # Стандартный поиск сервиса
    # Получаем список сервисов (из кэша)
    try:
        services = await FiveSimAPI.get_all_services_list()
    except Exception as e:
        logger.error(f"Error getting services list: {e}")
        return
    
    if not services:
        logger.warning("Services list is empty")
        return

    # Фильтруем
    filtered_services = [s for s in services if search_term in s.lower()]
    logger.info(f"Found {len(filtered_services)} services matching '{search_term}'")
    
    # Ограничиваем кол-во результатов (Telegram позволяет до 50)
    filtered_services = filtered_services[:50]
    
    results = []
    for service in filtered_services:
        # Уникальный ID для результата
        result_id = hashlib.md5(service.encode()).hexdigest()
        
        results.append(
            types.InlineQueryResultArticle(
                id=result_id,
                title=service.capitalize(),
                input_message_content=types.InputTextMessageContent(
                    message_text=f"***🔍 Поиск сервиса: {service}***",
                    parse_mode="Markdown"
                ),
                description="Нажмите, чтобы выбрать этот сервис"
            )
        )
        
    try:
        await query.answer(results, cache_time=300, is_personal=False)
        logger.info("Sent inline results")
    except Exception as e:
        logger.error(f"Error sending inline results: {e}")
