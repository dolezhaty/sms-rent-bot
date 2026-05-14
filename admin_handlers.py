"""
Админские команды для управления кастомными ценами.

Использование:
  /setprice <user_id> <service> <country> <price_usd>
  Пример: /setprice 7690030433 wallapop spain 0.30

  /delprice <user_id> <service> <country>
  Пример: /delprice 7690030433 wallapop spain

  /getprices <user_id>
  Пример: /getprices 7690030433
"""

import logging
from aiogram import types

import database
from handlers import dp
from src.config import is_admin

logger = logging.getLogger(__name__)


@dp.message_handler(commands=["setprice"])
async def cmd_setprice(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    args = message.get_args().split()
    if len(args) != 4:
        await message.reply("❌ Формат: /setprice <user_id> <service> <country> <price_usd>\nПример: /setprice 7690030433 wallapop spain 0.30")
        return

    try:
        user_id = int(args[0])
        service = args[1].lower()
        country = args[2].lower()
        price_usd = float(args[3])
    except ValueError:
        await message.reply("❌ Неверный формат. user_id — целое число, price_usd — дробное.")
        return

    user = await database.get_user(user_id)
    if not user:
        await message.reply(f"❌ Пользователь {user_id} не найден в БД.")
        return

    await database.set_custom_price(user_id, service, country, price_usd)

    tg = f"@{user.username}" if user.username else f"ID: {user_id}"
    await message.reply(
        f"✅ Кастомная цена установлена:\n"
        f"👤 Юзер: {tg}\n"
        f"📦 Сервис: {service}\n"
        f"🌍 Страна: {country}\n"
        f"💵 Цена: ${price_usd}"
    )


@dp.message_handler(commands=["delprice"])
async def cmd_delprice(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    args = message.get_args().split()
    if len(args) != 3:
        await message.reply("❌ Формат: /delprice <user_id> <service> <country>\nПример: /delprice 7690030433 wallapop spain")
        return

    try:
        user_id = int(args[0])
        service = args[1].lower()
        country = args[2].lower()
    except ValueError:
        await message.reply("❌ Неверный формат.")
        return

    await database.delete_custom_price(user_id, service, country)
    await message.reply(f"✅ Кастомная цена для {user_id} / {service} / {country} удалена. Теперь стандартная.")


@dp.message_handler(commands=["getprices"])
async def cmd_getprices(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    args = message.get_args().split()
    if len(args) != 1:
        await message.reply("❌ Формат: /getprices <user_id>")
        return

    try:
        user_id = int(args[0])
    except ValueError:
        await message.reply("❌ user_id должен быть числом.")
        return

    rows = await database.get_user_custom_prices(user_id)
    if not rows:
        await message.reply(f"У пользователя {user_id} нет кастомных цен — везде стандартная.")
        return

    lines = [f"💰 Кастомные цены для {user_id}:"]
    for r in rows:
        lines.append(f"  • {r.service} / {r.country} → ${r.price_usd}")
    await message.reply("\n".join(lines))
