
import aiohttp
import logging
from .base import BaseSMSProvider
from src.config import FIVESIM_TOKEN

logger = logging.getLogger(__name__)

class FiveSimProvider(BaseSMSProvider):
    BASE_URL = "https://5sim.net/v1"
    HEADERS = {
        "Authorization": f"Bearer {FIVESIM_TOKEN}",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    _services_cache = None
    
    # Резервный список сервисов, если API недоступен
    FALLBACK_SERVICES = sorted([
        "telegram", "whatsapp", "google", "facebook", "twitter", "instagram", "tiktok", "tinder", "viber", 
        "wechat", "snapchat", "linkedin", "uber", "discord", "steam", "netflix", "amazon", "paypal", 
        "microsoft", "yahoo", "vkontakte", "airbnb", "yandex", "mailru", "avito", "youla", "kakao", 
        "naver", "line", "kakaotalk", "ok", "okru", "mamba", "badoo", "pof", "bumble", "hinge", 
        "grindr", "blablacar", "bolt", "grab", "gojek", "foodpanda", "deliveroo", "glovo", "wolt", 
        "uber_eats", "doordash", "justeat", "shopee", "lazada", "aliexpress", "alibaba", "taobao", 
        "jd", "pinduoduo", "1688", "ebay", "vinted", "wallapop", "subito", "kleinanzeigen", "marktplaats",
        "olx", "craigslist", "offerup", "mercari", "poshmark", "depop", "carousell", "shpock", "gumtree"
    ])

    def __init__(self):
        self.session = None

    async def _get_session(self):
        if self.session is None or self.session.closed:
            # Увеличен таймаут до 30с для лучшей обработки лимитов и медленных ответов
            timeout = aiohttp.ClientTimeout(total=30, connect=15)
            
            # Внимание! Использование ssl=False в TCPConnector отключит проверку сертификатов.
            # Это может быть небезопасно, но решает проблему с SSL в локальной среде.
            connector = aiohttp.TCPConnector(ssl=False, limit=10) # Убрали force_close=True для переиспользования соединений
            self.session = aiohttp.ClientSession(timeout=timeout, connector=connector, headers=self.HEADERS)
        return self.session

    async def _request(self, method, endpoint, params=None, data=None):
        session = await self._get_session()
        url = f"{self.BASE_URL}{endpoint}"
        try:
            logger.info(f"5sim Request: {method} {url} Params: {params}")
            async with session.request(method, url, params=params, json=data) as response:
                if response.status != 200:
                    text = await response.text()
                    logger.error(f"5sim API Error: {response.status} - {text}")
                    return None
                
                # Check content type before parsing JSON
                if response.content_type == 'application/json':
                    return await response.json()
                else:
                    text = await response.text()
                    if "no free phones" in text.lower():
                        logger.warning(f"5sim: No free phones for request {endpoint}")
                        return {"error": "no_free_phones"}
                    
                    logger.warning(f"5sim API returned non-JSON response: {text}")
                    return None
                    
        except Exception as e:
            logger.error(f"5sim Request Failed: {e}")
            return None

    async def get_balance(self) -> float:
        data = await self._request("GET", "/user/profile")
        if data and 'balance' in data:
            return float(data['balance'])
        return 0.0

    async def get_prices(self, country=None, product=None):
        logger.info(f"Getting prices for {country}/{product}...")
        params = {}
        if country: params['country'] = country
        if product: params['product'] = product
        
        # Получаем цены
        response = await self._request("GET", "/guest/prices", params=params)
        logger.info(f"Got prices response for {country}/{product}: {response is not None}")
        
        # Если API вернул ошибку, попробуем вернуть пустой dict
        if response is None:
            logger.warning(f"5sim returned None for prices. Country: {country}, Product: {product}")
            if product:
                return {product: {}} 
            return {}
            
        # Normalize response if country and product are specified
        # API returns {country: {product: {...}}} but we expect {product: {...}}
        if country and product and country in response:
            return response[country]
            
        return response

    async def buy_number(self, country, operator, product):
        return await self._request("GET", f"/user/buy/activation/{country}/{operator}/{product}")

    async def check_order(self, order_id):
        return await self._request("GET", f"/user/check/{order_id}")

    async def finish_order(self, order_id):
        return await self._request("GET", f"/user/finish/{order_id}")

    async def cancel_order(self, order_id):
        return await self._request("GET", f"/user/cancel/{order_id}")

    async def ban_order(self, order_id):
        return await self._request("GET", f"/user/ban/{order_id}")

    async def get_countries(self):
        return await self._request("GET", "/guest/countries")
        
    async def get_all_services_list(self):
        """Получить список всех уникальных сервисов (с кэшированием и фоллбэком)"""
        if self._services_cache:
            return self._services_cache
        
        logger.info("Загружаем список сервисов из 5sim...")
        prices = await self.get_prices()
        
        if not prices:
            logger.error("Не удалось получить цены от 5sim. Используем резервный список.")
            return self.FALLBACK_SERVICES
            
        services = set()
        for country_data in prices.values():
            if isinstance(country_data, dict):
                services.update(country_data.keys())
        
        if not services:
             logger.warning("Список сервисов пуст после парсинга. Используем резервный список.")
             return self.FALLBACK_SERVICES

        sorted_services = sorted(list(services))
        logger.info(f"Загружено {len(sorted_services)} сервисов")
        self._services_cache = sorted_services
        return sorted_services

    async def get_countries_for_service(self, service):
        """
        Get list of (country_code, country_name) for a specific service.
        """
        prices = await self.get_prices(product=service)
        
        if not prices:
            logger.warning(f"No prices returned for service: {service}")
            return []
            
        # Debug logging to understand structure
        keys = list(prices.keys())
        logger.info(f"Price keys for {service}: {keys[:5]} (Total: {len(keys)})")
        
        # Check if the root key is the service itself (API anomaly?)
        if len(keys) == 1 and keys[0] == service:
            logger.info(f"API returned service as root key. Digging deeper.")
            prices = prices[service]
            keys = list(prices.keys())
            
        country_codes = keys
        
        result = []
        from bin.country_utils import get_country_info
        
        for code in country_codes:
            # Skip if code matches service name (just in case)
            if code == service:
                continue
                
            info = get_country_info(code)
            if info:
                name = info['name']
            else:
                name = code.title()
            result.append((code, name))
            
        # Sort by name
        result.sort(key=lambda x: x[1])
        return result

    def get_country_flag(self, country_code):
        from bin.country_utils import get_country_info
        info = get_country_info(country_code)
        if info:
            return info['flag']
        return "🌍"

    async def close(self):
        if self.session:
            await self.session.close()
