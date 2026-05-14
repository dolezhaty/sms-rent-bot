"""
Модуль для работы с xRocket API
"""

import aiohttp
import json
import logging
from src.config import XROCKET_TOKEN

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class XRocket:
    def __init__(self):
        self.token = XROCKET_TOKEN
        self.base_url = "https://pay.xrocket.tg"
        self.headers = {
            "Rocket-Pay-Key": self.token,
            "Content-Type": "application/json"
        }
        self._session = None

    async def get_session(self):
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(ssl=False)
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self._session

    async def _request(self, method, endpoint, params=None, data=None):
        url = f"{self.base_url}/{endpoint}"
        session = await self.get_session()
        
        logger.info(f"xRocket Request: {method} {url}")
        
        try:
            if method == "GET":
                async with session.get(url, headers=self.headers, params=params) as response:
                    return await self._handle_response(response)
            elif method == "POST":
                async with session.post(url, headers=self.headers, json=data) as response:
                    return await self._handle_response(response)
        except aiohttp.ClientConnectorError as e:
            logger.error(f"xRocket Connection Error: {e}")
            raise Exception(f"Ошибка подключения к xRocket API. ({e})")
        except Exception as e:
            logger.error(f"xRocket Request Error: {e}", exc_info=True)
            raise Exception(f"Ошибка запроса к xRocket: {str(e)}")

    async def _handle_response(self, response):
        try:
            result = await response.json()
        except Exception:
            text = await response.text()
            logger.error(f"xRocket Invalid JSON: {text[:200]}")
            raise Exception(f"Некорректный ответ от API (HTTP {response.status})")

        if response.status in [200, 201]:
            if result.get("success") or "data" in result:
                return result.get("data")
            else:
                message = result.get("message", "Unknown error")
                logger.error(f"xRocket API Error: {message}")
                raise Exception(f"Ошибка API: {message}")
        elif response.status == 401:
            logger.error("xRocket API Error: Unauthorized")
            raise Exception("Ошибка авторизации: проверьте XROCKET_TOKEN")
        else:
            message = result.get("message", "Unknown error")
            logger.error(f"xRocket HTTP {response.status}: {message}")
            raise Exception(f"Ошибка HTTP {response.status}: {message}")

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def create_invoice(self, amount: float, currency: str = "USDT", description: str = "", payload: str = None):
        """
        Создание инвойса для оплаты (tg-invoices)
        """
        data = {
            "amount": float(amount),
            "currency": currency,
            "description": description,
            "hiddenMessage": "Спасибо за оплату!"
        }
        if payload:
            data["payload"] = payload
            
        return await self._request("POST", "tg-invoices", data=data)

    async def get_invoice(self, invoice_id):
        """
        Получение информации об инвойсе
        """
        return await self._request("GET", f"tg-invoices/{invoice_id}")

    async def get_me(self):
        """
        Получение информации о приложении
        """
        return await self._request("GET", "app/info")


# Создаем глобальный экземпляр
xrocket = XRocket()
