from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, HTTPException, Response, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from jose import jwt
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import asyncio
import csv
import hashlib
import json
import logging
from io import StringIO
import bcrypt

import database
from loader import bot
from src.config import DIR, ADMIN_USERNAME, ADMIN_PASSWORD, SECRET_KEY, CRYPTOBOT_TOKEN, XROCKET_TOKEN

# Настройка логирования для вебхуков
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Hash the password for comparison if it's not already hashed
# In a real app, you'd store the hash in a database or config
def get_password_hash(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

# For this demo/setup, we'll hash the password from config once
# Ideally, settings.ini should contain the hash, not the plain password
STORED_PASSWORD_HASH = get_password_hash(ADMIN_PASSWORD)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    await database.create_tables()
    yield
    # Shutdown logic (if any)

app = FastAPI(title="Bot Admin Panel", version="0.1.0", lifespan=lifespan)

from api.api_v1 import api_router
app.include_router(api_router)

# Глобальное логирование всех запросов
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Фильтр для скрытия попыток сканирования конфиденциальных файлов
    path = request.url.path.lower()
    blocked_extensions = ['.env', '.php', '.git', '.sql', '.bak', '.aws', 'config.json']
    if any(ext in path for ext in blocked_extensions):
        logger.warning(f"BLOCKED SCANNING ATTEMPT: {request.method} {request.url.path} from {request.client.host}")
        return Response(content="Not Found", status_code=404)
        
    logger.info(f"ВХОДЯЩИЙ ЗАПРОС: {request.method} {request.url.path} от {request.client.host}")
    response = await call_next(request)
    logger.info(f"ОТВЕТ: {response.status_code} для {request.method} {request.url.path}")
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_admin(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username != ADMIN_USERNAME:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return {"username": username}
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.post("/auth/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username != ADMIN_USERNAME or not verify_password(form_data.password, STORED_PASSWORD_HASH):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token = create_access_token({"sub": ADMIN_USERNAME})
    return {"access_token": token, "token_type": "bearer"}

# ---------- Webhooks (CryptoBot) ----------

def verify_cryptobot_signature(request_body: bytes, signature: str) -> bool:
    """
    Проверка подписи вебхука от CryptoBot.
    Алгоритм: SHA256(token) в качестве ключа для HMAC, тело запроса как данные.
    """
    if not CRYPTOBOT_TOKEN:
        logger.error("CRYPTOBOT_TOKEN не настроен в конфигурации!")
        return False
        
    token_hash = hashlib.sha256(CRYPTOBOT_TOKEN.encode()).digest()
    hmac_check = hashlib.sha256(token_hash) # Упрощенная проверка через sha256 от токена как ключа
    # В документации CryptoBot: signature = hmac_sha256(sha256(token), body)
    import hmac
    expected_signature = hmac.new(token_hash, request_body, hashlib.sha256).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)

@app.get("/webhook/cryptobot")
async def cryptobot_webhook_test():
    return {"status": "ok", "message": "CryptoBot webhook endpoint is active. Use POST for actual updates."}

@app.post("/webhook/cryptobot")
async def cryptobot_webhook(request: Request):
    """
    Эндпоинт для приема уведомлений от CryptoBot
    """
    signature = request.headers.get("crypto-pay-api-signature")
    if not signature:
        logger.warning("Получен вебхук без подписи!")
        raise HTTPException(status_code=400, detail="Missing signature")

    body = await request.body()
    
    # Проверка подписи
    if not verify_cryptobot_signature(body, signature):
        logger.warning(f"Неверная подпись вебхука! Signature: {signature}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        data = json.loads(body)
        update_type = data.get("update_type")
        payload = data.get("payload", {})
        
        logger.info(f"Получен вебхук CryptoBot: {update_type}")

        if update_type == "invoice_paid":
            invoice_id = payload.get("invoice_id")
            status = payload.get("status")
            amount = payload.get("amount")
            asset = payload.get("asset")
            user_id_payload = payload.get("payload") # Мы передавали user_id сюда
            
            if status == "paid":
                logger.info(f"Инвойс {invoice_id} оплачен на сумму {amount} {asset}. UserID: {user_id_payload}")
                
                # 1. Пытаемся найти по payload (самый надежный способ для пополнения баланса)
                if user_id_payload and str(user_id_payload).isdigit():
                    user_id = int(user_id_payload)
                    amount_val = float(amount)
                    
                    # Проверяем, не было ли уже зачисления
                    if not await database.check_topup_exists(invoice_id):
                        # Атомарно обновляем баланс
                        await database.update_user_balance(user_id, amount_val)
                        # Регистрируем пополнение в таблице topups
                        await database.add_topup(user_id, invoice_id, amount_val, amount_val)
                        
                        # Добавляем в логи
                        user_data_log = await database.get_user(user_id)
                        username_log = user_data_log.username if user_data_log and user_data_log.username else "no_username"
                        await database.add_action_log(
                            user_id=user_id,
                            username=username_log,
                            action_type="topup",
                            details=f"Пополнение баланса на ${amount_val} через CryptoBot (Invoice: {invoice_id})"
                        )
                        
                        # Получаем информацию о платеже, чтобы найти message_id
                        payment_info = await database.get_payment_by_invoice(invoice_id)
                        
                        # Удаляем сообщение со счетом (с анимацией "распыления" в клиенте)
                        if payment_info and payment_info.get('message_id'):
                            try:
                                await bot.delete_message(payment_info['chat_id'] or user_id, payment_info['message_id'])
                                logger.info(f"Сообщение о счете {invoice_id} удалено.")
                            except Exception as del_error:
                                logger.error(f"Не удалось удалить сообщение о счете: {del_error}")

                        # Получаем новый баланс для уведомления
                        new_balance = await database.get_user_balance(user_id)
                        
                            # Отправляем уведомление пользователю
                        try:
                            text = (
                                f"✅ <b>Баланс успешно пополнен на ${amount_val}!</b>\n"
                                f"💰 <b>Текущий баланс: ${round(new_balance, 2)}</b>"
                            )
                            await bot.send_message(user_id, text, parse_mode="HTML")
                            logger.info(f"Уведомление о пополнении отправлено пользователю {user_id}")
                            
                            # --- Реферальная система ---
                            user_data = await database.get_user(user_id)
                            if user_data and user_data.inviting and user_data.inviting != 0:
                                referrer_id = user_data.inviting
                                bonus_amount = round(amount_val * 0.1, 2) # 10%
                                
                                if bonus_amount > 0:
                                    # Начисляем бонус рефереру
                                    await database.update_user_balance(referrer_id, bonus_amount)
                                    # Записываем в историю
                                    await database.add_referral_history(referrer_id, user_id, amount_val, bonus_amount)
                                    
                                    # Уведомляем реферера
                                    referral_name = f"ID: {user_id}"
                                    if user_data.username:
                                        referral_name = f"@{user_data.username}"
                                    
                                    ref_text = (
                                        f"<tg-emoji emoji-id='5902335789798265487'>👤</tg-emoji> <b>Ваш реферал {referral_name} пополнил счет!</b>\n"
                                        f"<tg-emoji emoji-id='6041705726206808304'>💰</tg-emoji> <b>Вам начислено 10% бонуса: ${bonus_amount}</b>"
                                    )
                                    try:
                                        await bot.send_message(referrer_id, ref_text, parse_mode="HTML")
                                        logger.info(f"Реферальный бонус {bonus_amount} начислен {referrer_id} за пополнение {user_id}")
                                    except Exception as ref_send_error:
                                        logger.error(f"Не удалось отправить уведомление рефереру {referrer_id}: {ref_send_error}")
                            # ---------------------------
                            
                        except Exception as send_error:
                            logger.error(f"Не удалось отправить уведомление пользователю {user_id}: {send_error}")
                            
                        logger.info(f"Баланс пользователя {user_id} успешно пополнен на {amount_val} {asset} через Webhook.")
                    else:
                        logger.info(f"Инвойс {invoice_id} уже был обработан ранее.")
                    return {"ok": True}

                # 2. Если payload пуст, ищем в таблице платежей (для обратной совместимости или покупок)
                payment_info = await database.get_payment_by_invoice(invoice_id)
                
                if payment_info:
                    user_id = payment_info.get('user_id')
                    amount_val = float(payment_info.get('amount')) # Сумма, которую мы ожидали
                    
                    # Проверяем, не было ли уже зачисления
                    if payment_info.get('status') != 'paid':
                        # Атомарно обновляем баланс
                        await database.update_user_balance(user_id, amount_val)
                        # Обновляем статус платежа в базе
                        await database.update_payment_status(invoice_id, 'paid')
                        logger.info(f"Баланс пользователя {user_id} успешно пополнен на {amount_val} через Webhook (Payment lookup).")
                    else:
                        logger.info(f"Инвойс {invoice_id} уже был обработан ранее.")
                else:
                    logger.warning(f"Информация об инвойсе {invoice_id} не найдена в базе данных!")

        return {"ok": True}

    except Exception as e:
        logger.error(f"Ошибка при обработке вебхука: {str(e)}")
        return {"ok": False, "error": str(e)}

# ---------- Webhooks (xRocket) ----------

def verify_xrocket_signature(request_body: bytes, signature: str) -> bool:
    """
    Проверка подписи вебхука от xRocket.
    Алгоритм: HMAC-SHA-256(SHA256(token), body)
    """
    if not XROCKET_TOKEN:
        logger.error("XROCKET_TOKEN не настроен!")
        return False
        
    import hmac
    token_hash = hashlib.sha256(XROCKET_TOKEN.encode()).digest()
    expected_signature = hmac.new(token_hash, request_body, hashlib.sha256).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)

@app.get("/webhook/xrocket")
async def xrocket_webhook_test():
    return {"status": "ok", "message": "xRocket webhook endpoint is active. Use POST for actual updates."}

@app.post("/webhook/xrocket")
async def xrocket_webhook(request: Request):
    """
    Эндпоинт для приема уведомлений от xRocket
    """
    # xRocket присылает подпись в заголовке 'Rocket-Pay-Signature'
    signature = request.headers.get("rocket-pay-signature")
    if not signature:
        # Также пробуем заголовок с другим регистром, если FastAPI его не нормализовал
        signature = request.headers.get("Rocket-Pay-Signature")
        
    if not signature:
        logger.warning(f"Получен вебхук xRocket без подписи! Headers: {request.headers.keys()}")
        raise HTTPException(status_code=400, detail="Missing signature")

    body = await request.body()
    
    # Логируем тело для отладки, если что-то не так
    # logger.debug(f"xRocket Webhook Body: {body.decode()}")
    
    if not verify_xrocket_signature(body, signature):
        logger.warning(f"Неверная подпись xRocket! Signature: {signature}")
        # xRocket требует 400 или 401 при неверной подписи
        raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        data = json.loads(body)
        
        # Анализ структуры xRocket по реальному логу:
        # { 'type': 'invoicePay', 'data': { 'id': '...', 'status': 'paid', 'payload': '...', ... } }
        invoice = data.get("data")
        if not invoice or not isinstance(invoice, dict) or "id" not in invoice:
            # Запасной вариант на случай другой структуры
            invoice = data.get("invoice")
            
        if not invoice:
            logger.error(f"Вебхук xRocket не содержит данных инвойса: {data}")
            return {"ok": False, "error": "No invoice data"}

        status = invoice.get("status")
        invoice_id = str(invoice.get("id"))
        amount = float(invoice.get("amount", 0))
        payload_data = invoice.get("payload")
        
        logger.info(f"Получен вебхук xRocket. Статус: {status}, ID: {invoice_id}, Payload: {payload_data}")

        # Статус оплаченного инвойса в xRocket - 'paid'
        if status == "paid" or status == "PAID":
            if payload_data and str(payload_data).isdigit():
                user_id = int(payload_data)
                
                # Проверяем, не обрабатывали ли мы этот инвойс ранее
                if not await database.check_topup_exists(invoice_id):
                    # Начисляем баланс
                    await database.update_user_balance(user_id, amount)
                    # Добавляем в историю пополнений (RUB = USD здесь для простоты, если валюта USDT)
                    await database.add_topup(user_id, invoice_id, amount, amount)
                    
                    # Добавляем в логи действий
                    user_data_log = await database.get_user(user_id)
                    username_log = user_data_log.username if user_data_log and user_data_log.username else "no_username"
                    await database.add_action_log(
                        user_id=user_id,
                        username=username_log,
                        action_type="topup",
                        details=f"Пополнение баланса на ${amount} через xRocket (Invoice: {invoice_id})"
                    )
                    
                    # Отправляем уведомление пользователю в боте
                    new_balance = await database.get_user_balance(user_id)
                    try:
                        text = (
                            f"✅ <b>Баланс успешно пополнен на ${amount}!</b>\n"
                            f"💰 <b>Текущий баланс: ${round(new_balance, 2)}</b>"
                        )
                        await bot.send_message(user_id, text, parse_mode="HTML")
                        
                        # Обработка реферальной программы (10% бонус)
                        user_data = await database.get_user(user_id)
                        if user_data and user_data.inviting and user_data.inviting != 0:
                            referrer_id = user_data.inviting
                            bonus_amount = round(amount * 0.1, 2)
                            if bonus_amount > 0:
                                await database.update_user_balance(referrer_id, bonus_amount)
                                await database.add_referral_history(referrer_id, user_id, amount, bonus_amount)
                                referral_name = f"ID: {user_id}"
                                if user_data.username:
                                    referral_name = f"@{user_data.username}"
                                
                                ref_text = (
                                    f"<tg-emoji emoji-id='5902335789798265487'>👤</tg-emoji> <b>Ваш реферал {referral_name} пополнил счет!</b>\n"
                                    f"<tg-emoji emoji-id='6041705726206808304'>💰</tg-emoji> <b>Вам начислено 10% бонуса: ${bonus_amount}</b>"
                                )
                                await bot.send_message(referrer_id, ref_text, parse_mode="HTML")
                    except Exception as e:
                        logger.error(f"Ошибка отправки уведомления xRocket: {e}")
                else:
                    logger.info(f"Инвойс xRocket {invoice_id} уже обработан ранее.")
            else:
                logger.warning(f"xRocket Webhook: отсутствует или некорректный payload (user_id): {payload_data}")

        return {"ok": True}
    except Exception as e:
        logger.error(f"Ошибка обработки вебхука xRocket: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}

# ---------- UI (Single Page Application) ----------

@app.get("/", response_class=HTMLResponse)
async def dashboard_ui():
    return """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Bot Admin Dashboard</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
            body { font-family: 'Inter', sans-serif; background-color: #0f172a; color: #f8fafc; }
            .card { background-color: #1e293b; border: 1px solid #334155; border-radius: 1rem; }
            .gradient-bg { background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); }
            .sidebar-item { transition: all 0.2s; }
            .sidebar-item:hover { background-color: #334155; border-radius: 0.5rem; }
            .sidebar-item.active { background-color: #2563eb; border-radius: 0.5rem; }
            input { background-color: #334155; border: 1px solid #475569; color: white; padding: 0.5rem 1rem; border-radius: 0.5rem; }
            .hidden { display: none; }
        </style>
    </head>
    <body class="min-h-screen flex">
        <!-- Login Modal -->
        <div id="login-modal" class="fixed inset-0 bg-black bg-opacity-80 flex items-center justify-center z-50">
            <div class="card p-8 w-full max-w-md">
                <div class="text-center mb-8">
                    <h1 class="text-3xl font-bold text-white mb-2">Вход в панель</h1>
                    <p class="text-slate-400">Введите данные администратора</p>
                </div>
                <form id="login-form" class="space-y-4">
                    <div>
                        <label class="block text-sm font-medium text-slate-400 mb-1">Логин</label>
                        <input type="text" id="username" class="w-full" value="admin" required>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-400 mb-1">Пароль</label>
                        <input type="password" id="password" class="w-full" value="admin123" required>
                    </div>
                    <button type="submit" class="w-full gradient-bg text-white font-bold py-3 rounded-lg hover:opacity-90 transition shadow-lg shadow-blue-500/20">Войти</button>
                    <p id="login-error" class="text-red-500 text-sm text-center hidden mt-2">Неверные данные</p>
                </form>
            </div>
        </div>

        <!-- Sidebar -->
        <aside class="w-64 border-r border-slate-800 p-6 hidden md:block" id="sidebar">
            <div class="flex items-center gap-3 mb-10">
                <div class="w-10 h-10 gradient-bg rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/20">
                    <i class="fas fa-robot text-white text-xl"></i>
                </div>
                <h2 class="text-xl font-bold tracking-tight">Saint's <span class="text-blue-500">Sms</span></h2>
            </div>
            
            <nav class="space-y-2">
                <a href="#" onclick="showPage('dashboard')" class="sidebar-item active flex items-center gap-3 px-4 py-3 text-slate-300 hover:text-white" id="nav-dashboard">
                    <i class="fas fa-chart-line w-5 text-center"></i>
                    <span class="font-medium">Дашборд</span>
                </a>
                <a href="#" onclick="showPage('orders')" class="sidebar-item flex items-center gap-3 px-4 py-3 text-slate-300 hover:text-white" id="nav-orders">
                    <i class="fas fa-shopping-cart w-5 text-center"></i>
                    <span class="font-medium">Заказы</span>
                </a>
                <a href="#" onclick="showPage('users')" class="sidebar-item flex items-center gap-3 px-4 py-3 text-slate-300 hover:text-white" id="nav-users">
                    <i class="fas fa-users w-5 text-center"></i>
                    <span class="font-medium">Пользователи</span>
                </a>
                <a href="#" onclick="showPage('referral')" class="sidebar-item flex items-center gap-3 px-4 py-3 text-slate-300 hover:text-white" id="nav-referral">
                    <i class="fas fa-handshake w-5 text-center"></i>
                    <span class="font-medium">Рефералы</span>
                </a>
                <a href="#" onclick="showPage('finance')" class="sidebar-item flex items-center gap-3 px-4 py-3 text-slate-300 hover:text-white" id="nav-finance">
                    <i class="fas fa-wallet w-5 text-center"></i>
                    <span class="font-medium">Финансы</span>
                </a>
                <a href="#" onclick="showPage('logs')" class="sidebar-item flex items-center gap-3 px-4 py-3 text-slate-300 hover:text-white" id="nav-logs">
                    <i class="fas fa-history w-5 text-center"></i>
                    <span class="font-medium">Логи</span>
                </a>
            </nav>

            <div class="mt-auto pt-10">
                <button onclick="logout()" class="flex items-center gap-3 px-4 py-3 text-slate-400 hover:text-red-400 transition w-full">
                    <i class="fas fa-sign-out-alt w-5 text-center"></i>
                    <span class="font-medium">Выйти</span>
                </button>
            </div>
        </aside>

        <!-- Main Content -->
        <main class="flex-1 p-8 overflow-y-auto hidden" id="main-content">
            <header class="flex justify-between items-center mb-10">
                <div>
                    <h1 class="text-2xl font-bold text-white mb-1" id="page-title">Дашборд</h1>
                    <p class="text-slate-400 text-sm">Обзор показателей магазина на сегодня</p>
                </div>
                <div class="flex gap-4">
                    <button onclick="refreshData()" class="card px-4 py-2 hover:bg-slate-800 transition text-sm flex items-center gap-2">
                        <i class="fas fa-sync-alt" id="refresh-icon"></i> Обновить
                    </button>
                    <div class="card px-4 py-2 flex items-center gap-3">
                        <div class="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center">
                            <i class="fas fa-user text-blue-500 text-xs"></i>
                        </div>
                        <span class="text-sm font-medium" id="admin-name">Admin</span>
                    </div>
                </div>
            </header>

            <!-- Dashboard Page -->
            <div id="page-dashboard" class="page-content space-y-8">
                <!-- Stats Grid -->
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                    <div class="card p-6">
                        <div class="flex justify-between items-start mb-4">
                            <div class="p-3 bg-blue-500/10 rounded-lg text-blue-500">
                                <i class="fas fa-shopping-bag text-xl"></i>
                            </div>
                            <span class="text-emerald-400 text-xs font-bold px-2 py-1 bg-emerald-400/10 rounded-full" id="orders-change">+0%</span>
                        </div>
                        <p class="text-slate-400 text-sm mb-1">Заказы сегодня</p>
                        <h3 class="text-3xl font-bold" id="orders-count">0</h3>
                    </div>
                    <div class="card p-6">
                        <div class="flex justify-between items-start mb-4">
                            <div class="p-3 bg-emerald-500/10 rounded-lg text-emerald-500">
                                <i class="fas fa-dollar-sign text-xl"></i>
                            </div>
                            <span class="text-slate-400 text-xs">Всего</span>
                        </div>
                        <p class="text-slate-400 text-sm mb-1">Выручка</p>
                        <h3 class="text-3xl font-bold" id="revenue-total">$0.00</h3>
                    </div>
                    <div class="card p-6">
                        <div class="flex justify-between items-start mb-4">
                            <div class="p-3 bg-purple-500/10 rounded-lg text-purple-500">
                                <i class="fas fa-coins text-xl"></i>
                            </div>
                            <span class="text-slate-400 text-xs">Чистая</span>
                        </div>
                        <p class="text-slate-400 text-sm mb-1">Прибыль</p>
                        <h3 class="text-3xl font-bold" id="profit-total">$0.00</h3>
                    </div>
                    <div class="card p-6">
                        <div class="flex justify-between items-start mb-4">
                            <div class="p-3 bg-orange-500/10 rounded-lg text-orange-500">
                                <i class="fas fa-user-plus text-xl"></i>
                            </div>
                            <span class="text-slate-400 text-xs">Новые</span>
                        </div>
                        <p class="text-slate-400 text-sm mb-1">Пользователи</p>
                        <h3 class="text-3xl font-bold" id="users-count">0</h3>
                    </div>
                </div>

                <!-- Charts Row -->
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <div class="card p-6 h-[400px] flex flex-col">
                        <h4 class="font-bold mb-6 flex items-center gap-2">
                            <i class="fas fa-chart-area text-blue-500"></i> Динамика продаж
                        </h4>
                        <div class="flex-1 relative">
                            <canvas id="salesChart"></canvas>
                        </div>
                    </div>
                    <div class="card p-6 h-[400px] flex flex-col">
                        <h4 class="font-bold mb-6 flex items-center gap-2">
                            <i class="fas fa-chart-pie text-emerald-500"></i> Популярные сервисы
                        </h4>
                        <div class="flex-1 relative">
                            <canvas id="servicesChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Other pages -->
            <div id="page-orders" class="page-content hidden space-y-6">
                <div class="card overflow-hidden">
                    <table class="w-full text-left text-sm">
                        <thead class="bg-slate-800/50 text-slate-400 font-medium">
                            <tr>
                                <th class="px-6 py-4">ID / Дата</th>
                                <th class="px-6 py-4">TG</th>
                                <th class="px-6 py-4">Сервис</th>
                                <th class="px-6 py-4">Страна</th>
                                <th class="px-6 py-4">Номер</th>
                                <th class="px-6 py-4">Цена</th>
                                <th class="px-6 py-4">Статус</th>
                            </tr>
                        </thead>
                        <tbody id="orders-table-body" class="divide-y divide-slate-800">
                            <!-- Orders dynamic -->
                        </tbody>
                    </table>
                </div>
            </div>

            <div id="page-users" class="page-content hidden space-y-6">
                <div class="card overflow-hidden">
                    <table class="w-full text-left text-sm">
                        <thead class="bg-slate-800/50 text-slate-400 font-medium">
                            <tr>
                                <th class="px-6 py-4">TG / ID</th>
                                <th class="px-6 py-4">Заказов</th>
                                <th class="px-6 py-4">Потрачено</th>
                                <th class="px-6 py-4">Баланс</th>
                                <th class="px-6 py-4">Регистрация</th>
                            </tr>
                        </thead>
                        <tbody id="users-table-body" class="divide-y divide-slate-800">
                            <!-- Users dynamic -->
                        </tbody>
                    </table>
                </div>
            </div>

            <div id="page-finance" class="page-content hidden space-y-8">
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div class="card p-6 border-l-4 border-red-500">
                        <p class="text-slate-400 text-sm mb-1">Потрачено в 5sim</p>
                        <h3 class="text-2xl font-bold" id="fin-5sim">$0.00</h3>
                    </div>
                    <div class="card p-6 border-l-4 border-blue-500">
                        <p class="text-slate-400 text-sm mb-1">Общая выручка</p>
                        <h3 class="text-2xl font-bold" id="fin-revenue">$0.00</h3>
                    </div>
                    <div class="card p-6 border-l-4 border-emerald-500">
                        <p class="text-slate-400 text-sm mb-1">Чистая прибыль</p>
                        <h3 class="text-2xl font-bold" id="fin-profit">$0.00</h3>
                    </div>
                </div>

                <div class="card p-8">
                    <h4 class="text-xl font-bold mb-6 flex items-center gap-2">
                        <i class="fas fa-users-cog text-blue-500"></i> Распределение прибыли (33.3%)
                    </h4>
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-8" id="owners-grid">
                        <!-- Owners dynamic -->
                    </div>
                </div>
            </div>

            <div id="page-referral" class="page-content hidden space-y-8">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div class="card p-6">
                        <p class="text-slate-400 text-sm mb-1">Всего рефералов</p>
                        <h3 class="text-3xl font-bold" id="ref-count">0</h3>
                    </div>
                    <div class="card p-6">
                        <p class="text-slate-400 text-sm mb-1">Выплачено бонусов</p>
                        <h3 class="text-3xl font-bold text-emerald-400" id="ref-bonus">$0.00</h3>
                    </div>
                </div>

                <div class="card p-8">
                    <h4 class="text-xl font-bold mb-6 flex items-center gap-2">
                        <i class="fas fa-crown text-yellow-500"></i> Топ рефереров
                    </h4>
                    <div class="overflow-hidden">
                        <table class="w-full text-left text-sm">
                            <thead class="bg-slate-800/50 text-slate-400 font-medium">
                                <tr>
                                    <th class="px-6 py-4">Пользователь</th>
                                    <th class="px-6 py-4">Заработано</th>
                                </tr>
                            </thead>
                            <tbody id="ref-table-body" class="divide-y divide-slate-800">
                                <!-- Top referrers dynamic -->
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <div id="page-logs" class="page-content hidden space-y-6">
                <div class="card overflow-hidden">
                    <table class="w-full text-left text-sm">
                        <thead class="bg-slate-800/50 text-slate-400 font-medium">
                            <tr>
                                <th class="px-6 py-4">Дата / Время</th>
                                <th class="px-6 py-4">Пользователь</th>
                                <th class="px-6 py-4">Действие</th>
                                <th class="px-6 py-4">Детали</th>
                            </tr>
                        </thead>
                        <tbody id="logs-table-body" class="divide-y divide-slate-800">
                            <!-- Logs dynamic -->
                        </tbody>
                    </table>
                </div>
            </div>
        </main>

        <script>
            let token = localStorage.getItem('admin_token');
            let charts = {};

            // Auth Check
            if (token) {
                document.getElementById('login-modal').classList.add('hidden');
                document.getElementById('main-content').classList.remove('hidden');
                document.getElementById('sidebar').classList.remove('hidden');
                refreshData();
            }

            // Login
             document.getElementById('login-form').onsubmit = async (e) => {
                 e.preventDefault();
                 console.log("Login attempt...");
                 const formData = new URLSearchParams();
                 formData.append('username', document.getElementById('username').value);
                 formData.append('password', document.getElementById('password').value);

                 try {
                     const res = await fetch('/auth/login', { 
                         method: 'POST', 
                         headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                         body: formData 
                     });
                     console.log("Response status:", res.status);
                     if (res.ok) {
                         const data = await res.json();
                         token = data.access_token;
                         localStorage.setItem('admin_token', token);
                         location.reload();
                     } else {
                         const errData = await res.json();
                         console.error("Login failed:", errData);
                         document.getElementById('login-error').classList.remove('hidden');
                     }
                 } catch (err) {
                     console.error("Fetch error:", err);
                     alert("Ошибка подключения к серверу");
                 }
             };

            function logout() {
                localStorage.removeItem('admin_token');
                location.reload();
            }

            let activePage = 'dashboard';

            function showPage(pageId) {
                activePage = pageId;
                document.querySelectorAll('.page-content').forEach(p => p.classList.add('hidden'));
                document.getElementById('page-' + pageId).classList.remove('hidden');
                
                document.querySelectorAll('.sidebar-item').forEach(i => i.classList.remove('active'));
                document.getElementById('nav-' + pageId).classList.add('active');
                
                const titles = { 'dashboard': 'Дашборд', 'orders': 'Заказы', 'users': 'Пользователи', 'finance': 'Финансы', 'referral': 'Рефералы', 'logs': 'Логи' };
                document.getElementById('page-title').innerText = titles[pageId];

                if (pageId === 'orders') loadOrders();
                if (pageId === 'users') loadUsers();
                if (pageId === 'finance') loadDetailedFinance();
                if (pageId === 'referral') loadReferralStats();
                if (pageId === 'logs') loadActionLogs();
            }

            async function loadActionLogs() {
                const data = await apiFetch('/logs/all');
                const tbody = document.getElementById('logs-table-body');
                tbody.innerHTML = data.logs.map(l => `
                    <tr class="hover:bg-slate-800/30 transition">
                        <td class="px-6 py-4 text-slate-400 font-mono text-xs">${l.timestamp}</td>
                        <td class="px-6 py-4 text-blue-400 font-medium">${l.username}</td>
                        <td class="px-6 py-4">
                            <span class="px-2 py-1 rounded text-xs font-bold ${
                                l.action_type === 'topup' ? 'bg-emerald-500/10 text-emerald-500' : 
                                l.action_type === 'purchase' ? 'bg-blue-500/10 text-blue-400' : 
                                l.action_type === 'sms_received' ? 'bg-purple-500/10 text-purple-400' : 'bg-slate-700 text-slate-300'
                            }">${l.action_type.toUpperCase()}</span>
                        </td>
                        <td class="px-6 py-4 text-slate-300 text-xs">${l.details}</td>
                    </tr>
                `).join('');
            }

            async function loadOrders() {
                const data = await apiFetch('/orders/all');
                const tbody = document.getElementById('orders-table-body');
                tbody.innerHTML = data.orders.map(o => `
                    <tr class="hover:bg-slate-800/30 transition">
                        <td class="px-6 py-4">
                            <div class="font-medium">#${o.id}</div>
                            <div class="text-xs text-slate-500">${o.date}</div>
                        </td>
                        <td class="px-6 py-4 text-blue-400 font-medium">${o.tg}</td>
                        <td class="px-6 py-4">${o.service}</td>
                        <td class="px-6 py-4">${o.country}</td>
                        <td class="px-6 py-4 font-mono">${o.phone}</td>
                        <td class="px-6 py-4 font-bold text-white">$${o.price}</td>
                        <td class="px-6 py-4">
                            <span class="px-2 py-1 rounded-full text-xs font-bold ${
                                o.status === 'FINISHED' ? 'bg-emerald-500/10 text-emerald-500' : 
                                o.status === 'PENDING' ? 'bg-blue-500/10 text-blue-400' : 'bg-red-500/10 text-red-400'
                            }">${o.status}</span>
                        </td>
                    </tr>
                `).join('');
            }

            async function loadUsers() {
                const data = await apiFetch('/users/all');
                const tbody = document.getElementById('users-table-body');
                tbody.innerHTML = data.users.map(u => `
                    <tr class="hover:bg-slate-800/30 transition">
                        <td class="px-6 py-4">
                            <div class="text-blue-400 font-medium">${u.tg}</div>
                            <div class="text-xs text-slate-500">ID: ${u.user_id}</div>
                        </td>
                        <td class="px-6 py-4">${u.order_count}</td>
                        <td class="px-6 py-4 font-bold text-white">$${u.total_spent}</td>
                        <td class="px-6 py-4 text-emerald-400">$${u.balance}</td>
                        <td class="px-6 py-4 text-slate-500">${u.reg_date}</td>
                    </tr>
                `).join('');
            }

            async function loadDetailedFinance() {
                const data = await apiFetch('/finance/detailed');
                document.getElementById('fin-5sim').innerText = '$' + data.cost_5sim.toFixed(2);
                document.getElementById('fin-revenue').innerText = '$' + data.total_sales.toFixed(2);
                document.getElementById('fin-profit').innerText = '$' + data.net_profit.toFixed(2);

                const grid = document.getElementById('owners-grid');
                grid.innerHTML = data.owners.map(o => `
                    <div class="p-6 rounded-2xl bg-slate-800/50 border border-slate-700">
                        <div class="flex items-center gap-4 mb-4">
                            <div class="w-12 h-12 rounded-full gradient-bg flex items-center justify-center text-white font-bold text-lg">
                                ${o.name[0].toUpperCase()}
                            </div>
                            <div>
                                <h5 class="font-bold text-white">${o.name}</h5>
                                <p class="text-xs text-slate-400">Владелец (33.3%)</p>
                            </div>
                        </div>
                        <p class="text-slate-400 text-sm mb-1">Заработано:</p>
                        <h4 class="text-3xl font-bold text-emerald-400">$${o.share.toFixed(2)}</h4>
                    </div>
                `).join('');
            }

            async function loadReferralStats() {
                const data = await apiFetch('/stats/referral');
                document.getElementById('ref-count').innerText = data.referral_count;
                document.getElementById('ref-bonus').innerText = '$' + data.total_bonus.toFixed(2);
                
                const tbody = document.getElementById('ref-table-body');
                tbody.innerHTML = data.top_referrers.map(r => `
                    <tr class="hover:bg-slate-800/30 transition">
                        <td class="px-6 py-4 font-medium text-blue-400">${r.tg}</td>
                        <td class="px-6 py-4 font-bold text-emerald-400">$${r.earnings.toFixed(2)}</td>
                    </tr>
                `).join('');
            }

            async function apiFetch(endpoint) {
                const res = await fetch(endpoint, {
                    headers: { 'Authorization': 'Bearer ' + token }
                });
                if (res.status === 401) logout();
                return await res.json();
            }

            async function refreshData() {
                const icon = document.getElementById('refresh-icon');
                icon.classList.add('fa-spin');
                
                try {
                    const [daily, finance, distribution, history] = await Promise.all([
                        apiFetch('/stats/daily'),
                        apiFetch('/finance/summary'),
                        apiFetch('/stats/services-distribution'),
                        apiFetch('/stats/sales-history')
                    ]);

                    // Update Stats
                    document.getElementById('orders-count').innerText = daily.orders_today;
                    document.getElementById('users-count').innerText = daily.users_total;
                    const changeEl = document.getElementById('orders-change');
                    changeEl.innerText = (daily.change_pct >= 0 ? '+' : '') + daily.change_pct + '%';
                    changeEl.className = daily.change_pct >= 0 ? 
                        'text-emerald-400 text-xs font-bold px-2 py-1 bg-emerald-400/10 rounded-full' : 
                        'text-red-400 text-xs font-bold px-2 py-1 bg-red-400/10 rounded-full';

                    document.getElementById('revenue-total').innerText = '$' + (daily.revenue_today || 0.00).toFixed(2);
                    document.getElementById('profit-total').innerText = '$' + finance.net_profit.toFixed(2);

                    updateCharts(distribution.distribution, history.history);

                    // --- ADDED: Refresh current page data ---
                    if (activePage === 'orders') await loadOrders();
                    if (activePage === 'users') await loadUsers();
                    if (activePage === 'finance') await loadDetailedFinance();
                    if (activePage === 'referral') await loadReferralStats();
                    if (activePage === 'logs') await loadActionLogs();

                } catch (err) {
                    console.error('Refresh error:', err);
                } finally {
                    setTimeout(() => icon.classList.remove('fa-spin'), 500);
                }
            }

            function updateCharts(dist, history) {
                // Services Chart
                const labels = dist.map(d => d.service);
                const data = dist.map(d => d.count);

                if (charts.services) charts.services.destroy();
                const ctx = document.getElementById('servicesChart').getContext('2d');
                charts.services = new Chart(ctx, {
                    type: 'doughnut',
                    data: {
                        labels: labels,
                        datasets: [{
                            data: data,
                            backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444', '#06b6d4'],
                            borderWidth: 0
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { position: 'bottom', labels: { color: '#94a3b8', padding: 20 } }
                        }
                    }
                });

                // Sales History Chart
                const hLabels = history.map(h => h.date);
                const hData = history.map(h => h.amount);

                if (charts.sales) charts.sales.destroy();
                const ctxSales = document.getElementById('salesChart').getContext('2d');
                charts.sales = new Chart(ctxSales, {
                    type: 'line',
                    data: {
                        labels: hLabels,
                        datasets: [{
                            label: 'Продажи ($)',
                            data: hData,
                            borderColor: '#3b82f6',
                            backgroundColor: 'rgba(59, 130, 246, 0.1)',
                            fill: true,
                            tension: 0.4
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: { grid: { color: '#334155' }, ticks: { color: '#94a3b8' } },
                            x: { grid: { display: false }, ticks: { color: '#94a3b8' } }
                        },
                        plugins: { legend: { display: false } }
                    }
                });
            }

            // WebSocket for live updates
            const ws = new WebSocket(`ws://${location.host}/ws`);
            ws.onmessage = (event) => {
                const msg = JSON.parse(event.data);
                if (msg.type === 'finance_summary') {
                    document.getElementById('revenue-total').innerText = '$' + msg.data.total_sales.toFixed(2);
                    document.getElementById('profit-total').innerText = '$' + msg.data.net_profit.toFixed(2);
                }
            };
        </script>
    </body>
    </html>
    """

# ---------- Статистика заказов ----------

@app.get("/stats/daily", dependencies=[Depends(get_current_admin)])
async def stats_daily():
    # Кол-во заказов (по таблице Orders) за сегодня
    from datetime import datetime, time as dt_time
    now = datetime.now()
    today_start = datetime.combine(now.date(), dt_time.min).timestamp()
    today_end = datetime.combine(now.date(), dt_time.max).timestamp()
    
    # Считаем заказы из таблицы Orders (SMS активации)
    orders_today = await database.get_orders_by_date(today_start, today_end)
    sms_count_today = len(orders_today)
    
    # Считаем продажи из таблицы Sales (Цифровые товары)
    sales_today = await database.get_daily_sales(now.strftime("%d.%m.%Y"))
    sales_count_today = len(sales_today)
    
    total_count_today = sms_count_today + sales_count_today
    
    # Изменено: Выручка на дашборде за сегодня (пополнения)
    async with database.async_session() as session:
        from src.database_models import Topup
        from sqlalchemy import select, func
        
        date_str = now.strftime("%d.%m.%Y")
        res = await session.execute(select(func.sum(Topup.amount_usd)).where(Topup.date.like(f"%{date_str}%")))
        revenue_today = res.scalar() or 0.0
    
    # Вчера
    from datetime import timedelta
    yesterday = now - timedelta(days=1)
    yesterday_start = datetime.combine(yesterday.date(), dt_time.min).timestamp()
    yesterday_end = datetime.combine(yesterday.date(), dt_time.max).timestamp()
    
    orders_yesterday = await database.get_orders_by_date(yesterday_start, yesterday_end)
    sms_count_yesterday = len(orders_yesterday)
    
    sales_yesterday = await database.get_daily_sales(yesterday.strftime("%d.%m.%Y"))
    sales_count_yesterday = len(sales_yesterday)
    
    total_count_yesterday = sms_count_yesterday + sales_count_yesterday
    
    change_pct = ((total_count_today - total_count_yesterday) / total_count_yesterday * 100) if total_count_yesterday else (100.0 if total_count_today else 0.0)
    
    # Общее кол-во пользователей
    all_users = await database.get_all_users()
    users_count = len(all_users)
    
    return {
        "orders_today": total_count_today, 
        "change_pct": round(change_pct, 2),
        "users_total": users_count,
        "revenue_today": round(revenue_today, 2)
    }

@app.get("/stats/sales-history", dependencies=[Depends(get_current_admin)])
async def stats_sales_history():
    # История пополнений за последние 7 дней (Реальный приход денег)
    from datetime import datetime, timedelta
    now = datetime.now()
    history = []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        date_str = day.strftime("%d.%m.%Y")
        
        async with database.async_session() as session:
            from src.database_models import Topup
            from sqlalchemy import select, func
            res = await session.execute(select(func.sum(Topup.amount_usd)).where(Topup.date.like(f"%{date_str}%")))
            amount = res.scalar() or 0.0
            
        history.append({"date": date_str, "amount": round(amount, 2)})
    return {"history": history}

@app.get("/stats/top-numbers", dependencies=[Depends(get_current_admin)])
async def stats_top_numbers(limit: int = 20):
    # Топ номеров по количеству завершенных заказов (по Sale нет номеров, берем из Orders, если статус FINISHED)
    # Требуется хранить успешные заказы с телефоном. Упростим: вернем последние PENDING по телефону.
    # Для реальной метрики нужна дополнительная модель, пока вернем пусто.
    return {"items": []}

@app.get("/stats/services-distribution", dependencies=[Depends(get_current_admin)])
async def stats_services_distribution():
    # Распределение по сервисам: считаем по Orders (всего записей)
    # Для простоты: активные заказы
    orders = await database.get_active_orders()
    by_service = {}
    for o in orders:
        by_service[o.service] = by_service.get(o.service, 0) + 1
    total = sum(by_service.values()) or 1
    result = [{"service": k, "count": v, "pct": round(v * 100 / total, 2)} for k, v in by_service.items()]
    return {"distribution": result}

@app.get("/stats/referral", dependencies=[Depends(get_current_admin)])
async def stats_referral():
    """
    Статистика реферальной системы для админ-панели
    """
    async with database.async_session() as session:
        from sqlalchemy import select, func
        from src.database_models import ReferralHistory, User
        
        # Общий заработок рефереров
        result_total = await session.execute(select(func.sum(ReferralHistory.amount_bonus)))
        total_bonus = result_total.scalar() or 0.0
        
        # Количество рефералов (у которых inviting != 0)
        result_count = await session.execute(select(func.count(User.user_id)).where(User.inviting != 0))
        referral_count = result_count.scalar() or 0
        
        # Топ рефереров
        result_top = await session.execute(
            select(ReferralHistory.referrer_id, func.sum(ReferralHistory.amount_bonus))
            .group_by(ReferralHistory.referrer_id)
            .order_by(func.sum(ReferralHistory.amount_bonus).desc())
            .limit(10)
        )
        top_referrers = []
        for row in result_top.all():
            user = await database.get_user(row[0])
            top_referrers.append({
                "tg": f"@{user.username}" if user and user.username else f"ID: {row[0]}",
                "earnings": round(row[1], 2)
            })
            
        return {
            "total_bonus": round(total_bonus, 2),
            "referral_count": referral_count,
            "top_referrers": top_referrers
        }

@app.get("/export/sales.csv", dependencies=[Depends(get_current_admin)])
async def export_sales_csv():
    sales = await database.get_all_sales()
    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "user_id", "item_name", "amount", "count", "date", "cheque"])
    for s in sales:
        writer.writerow([s.id, s.user_id, s.item_name, s.amount, s.count, s.date, s.cheque])
    return {"content": buf.getvalue()}

# ---------- Финансовый модуль ----------

@app.get("/finance/summary", dependencies=[Depends(get_current_admin)])
async def finance_summary():
    # Изменено: Выручка теперь считается по пополнениям (Topups)
    from src.config import CRYPTOBOT_COMMISSION
    
    # 1. Пополнения (Реальный приход денег)
    topups = await database.get_all_topups()
    total_revenue = sum([t.amount_usd for t in topups]) if topups else 0.0
    
    # 2. Расходы (Себестоимость СМС-активаций)
    orders = await database.get_all_orders()
    total_sms_cost = sum([o.price * 0.5 for o in orders if o.status == 'FINISHED']) if orders else 0.0
    
    # 3. Комиссии (на пополнения)
    commissions = round(total_revenue * CRYPTOBOT_COMMISSION, 4)
    
    net_profit = round(total_revenue - commissions - total_sms_cost, 4)
    return {
        "total_sales": round(total_revenue, 4),
        "commissions": commissions,
        "expenses": round(total_sms_cost, 4),
        "net_profit": net_profit
    }

@app.get("/orders/all", dependencies=[Depends(get_current_admin)])
async def get_all_orders_detailed():
    orders = await database.get_all_orders()
    result = []
    for o in orders:
        user = await database.get_user_by_id(o.user_id)
        username = f"@{user.username}" if user and user.username else f"ID: {o.user_id}"
        result.append({
            "id": o.id,
            "tg": username,
            "service": o.service,
            "country": o.country,
            "operator": o.operator,
            "phone": o.phone,
            "price": o.price,
            "status": o.status,
            "date": datetime.fromtimestamp(o.created_at).strftime("%d.%m %H:%M")
        })
    return {"orders": result}

@app.get("/users/all", dependencies=[Depends(get_current_admin)])
async def get_all_users_detailed():
    users = await database.get_all_users()
    result = []
    for u in users:
        sales = await database.get_user_buy(u.user_id)
        total_spent = sum([s.amount for s in sales])
        result.append({
            "user_id": u.user_id,
            "tg": f"@{u.username}" if u.username else f"ID: {u.user_id}",
            "order_count": len(sales),
            "total_spent": round(total_spent, 2),
            "balance": round(u.balance, 2),
            "reg_date": u.regDate
        })
    return {"users": result}

@app.get("/logs/all", dependencies=[Depends(get_current_admin)])
async def get_all_action_logs():
    logs = await database.get_action_logs(limit=100)
    result = []
    for log in logs:
        result.append({
            "id": log.id,
            "user_id": log.user_id,
            "username": f"@{log.username}" if log.username and log.username != "no_username" else f"ID: {log.user_id}",
            "action_type": log.action_type,
            "details": log.details,
            "timestamp": log.timestamp
        })
    return {"logs": result}

@app.get("/finance/detailed", dependencies=[Depends(get_current_admin)])
async def finance_detailed():
    from src.config import CRYPTOBOT_COMMISSION
    
    # Изменено: Используем пополнения
    topups = await database.get_all_topups()
    total_revenue = sum([t.amount_usd for t in topups]) if topups else 0.0
    
    # Затраты на СМС (50% от выручки с СМС)
    orders = await database.get_all_orders()
    total_sms_cost = sum([o.price * 0.5 for o in orders if o.status == 'FINISHED']) if orders else 0.0
    
    commissions = round(total_revenue * CRYPTOBOT_COMMISSION, 4)
    net_profit = round(total_revenue - commissions - total_sms_cost, 4)
    
    # Дележка между владельцами
    share = round(net_profit / 3, 4)
    
    return {
        "total_sales": round(total_revenue, 2),
        "cost_5sim": round(total_sms_cost, 2),
        "commissions": round(commissions, 2),
        "net_profit": round(net_profit, 2),
        "owners": [
            {"name": "awreti", "share": share},
            {"name": "alyx", "share": share},
            {"name": "qizrix", "share": share}
        ]
    }

@app.get("/pricing/all", dependencies=[Depends(get_current_admin)])
async def get_all_pricing():
    rows = await database.get_all_custom_prices()
    result = []
    for r in rows:
        user = await database.get_user(r.user_id)
        result.append({
            "id": r.id,
            "user_id": r.user_id,
            "tg": f"@{user.username}" if user and user.username else f"ID: {r.user_id}",
            "service": r.service,
            "country": r.country,
            "price_usd": r.price_usd
        })
    return {"pricing": result}

class PricingRequest(BaseModel):
    user_id: int
    service: str
    country: str
    price_usd: float

@app.post("/pricing/set", dependencies=[Depends(get_current_admin)])
async def set_pricing(req: PricingRequest):
    await database.set_custom_price(req.user_id, req.service, req.country, req.price_usd)
    return {"status": "ok", "user_id": req.user_id, "service": req.service, "country": req.country, "price_usd": req.price_usd}

@app.delete("/pricing/delete", dependencies=[Depends(get_current_admin)])
async def delete_pricing(user_id: int, service: str, country: str):
    await database.delete_custom_price(user_id, service, country)
    return {"status": "deleted"}

@app.get("/pricing/user/{user_id}", dependencies=[Depends(get_current_admin)])
async def get_user_pricing(user_id: int):
    rows = await database.get_user_custom_prices(user_id)
    return {"user_id": user_id, "pricing": [{"service": r.service, "country": r.country, "price_usd": r.price_usd} for r in rows]}

# ---------- WebSocket обновления ----------
connections: set[WebSocket] = set()

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connections.add(ws)
    try:
        while True:
            await asyncio.sleep(300)  # 5 минут
            summary = await finance_summary()
            await ws.send_json({"type": "finance_summary", "data": summary})
    except WebSocketDisconnect:
        connections.discard(ws)
    except Exception:
        connections.discard(ws)

@app.get("/health")
async def health_check():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}

if __name__ == "__main__":
    import uvicorn
    # На дедике обычно используют 0.0.0.0 для внешнего доступа
    print("\n" + "="*50)
    print("ЗАПУСК АДМИН-ПАНЕЛИ Saint's SMS")
    print("Хост: 0.0.0.0")
    print("Порт: 8080")
    print(f"Домен: shopup.sbs")
    print(f"Вебхук CryptoBot: https://shopup.sbs/webhook/cryptobot")
    print(f"Вебхук xRocket: https://shopup.sbs/webhook/xrocket")
    print("="*50 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8080)

