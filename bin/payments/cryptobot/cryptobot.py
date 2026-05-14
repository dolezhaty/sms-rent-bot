"""
Модуль для работы с CryptoBot API
"""

import aiohttp
import json
import logging
import hashlib
import hmac
from src.config import CRYPTOBOT_TOKEN

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CryptoBot:
    def __init__(self):
        self.token = CRYPTOBOT_TOKEN
        self.base_url = "https://pay.crypt.bot/api"
        self.headers = {
            "Crypto-Pay-API-Token": self.token,
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
        
        try:
            if method == "GET":
                async with session.get(url, headers=self.headers, params=params) as response:
                    return await self._handle_response(response)
            elif method == "POST":
                async with session.post(url, headers=self.headers, json=data) as response:
                    return await self._handle_response(response)
        except aiohttp.ClientConnectorError as e:
            logger.error(f"CryptoBot Connection Error: {e}")
            raise Exception(f"Ошибка подключения к CryptoBot API. Проверьте сеть или VPN. ({e})")
        except Exception as e:
            logger.error(f"CryptoBot Request Error: {e}", exc_info=True)
            raise Exception(f"Ошибка запроса к CryptoBot: {str(e)}")

    async def _handle_response(self, response):
        try:
            result = await response.json()
        except Exception:
            text = await response.text()
            logger.error(f"CryptoBot Invalid JSON: {text[:200]}")
            raise Exception(f"Некорректный ответ от API (HTTP {response.status})")

        if response.status == 200:
            if result.get("ok"):
                return result.get("result")
            else:
                error = result.get("error", {})
                error_name = error.get("name") if isinstance(error, dict) else str(error)
                logger.error(f"CryptoBot API Error: {error_name}")
                raise Exception(f"Ошибка API: {error_name}")
        elif response.status == 401:
            logger.error("CryptoBot API Error: Unauthorized")
            raise Exception("Ошибка авторизации: проверьте CRYPTOBOT_TOKEN")
        else:
            error = result.get("error", {})
            error_name = error.get("name") if isinstance(error, dict) else str(error)
            logger.error(f"CryptoBot HTTP {response.status}: {error_name}")
            raise Exception(f"Ошибка HTTP {response.status}: {error_name}")

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def create_invoice(self, amount: float, currency: str = "USDT", description: str = "", payload: str = None):
        """
        Создание инвойса для оплаты
        """
        data = {
            "asset": currency,
            "amount": "{:.6f}".format(amount).rstrip('0').rstrip('.'), # Форматируем число в строку без экспоненты
            "description": description
        }
        if payload:
            data["payload"] = payload
        return await self._request("POST", "createInvoice", data=data)

    async def get_invoices(self, invoice_ids: list = None, status: str = None, offset: int = 0, count: int = 100):
        """
        Получение списка инвойсов
        """
        params = {
            "offset": offset,
            "count": count
        }
        if invoice_ids:
            params["invoice_ids"] = ",".join(map(str, invoice_ids))
        if status:
            params["status"] = status
            
        result = await self._request("GET", "getInvoices", params=params)
        return result.get("items", []) if isinstance(result, dict) else result

    async def check_invoice_status(self, invoice_id):
        """
        Проверка статуса инвойса
        """
        invoices = await self.get_invoices(invoice_ids=[invoice_id])
        if invoices and len(invoices) > 0:
            return invoices[0].get("status")
        return None

    async def get_me(self):
        """
        Получение информации о боте
        """
        return await self._request("GET", "getMe")

    async def get_balance(self):
        """
        Получение баланса бота
        """
        return await self._request("GET", "getBalance")

    async def get_exchange_rates(self):
        """
        Получение курсов валют
        """
        return await self._request("GET", "getExchangeRates")

    async def set_webhook(self, webhook_url: str):
        """
        Настройка webhook
        """
        data = {"url": webhook_url}
        return await self._request("POST", "setWebhook", data=data)

    async def delete_webhook(self):
        """
        Удаление webhook
        """
        return await self._request("POST", "deleteWebhook")

    async def get_webhook_info(self):
        """
        Получение информации о webhook
        """
        return await self._request("GET", "getWebhookInfo")


# Создаем глобальный экземпляр
cryptobot = CryptoBot()
