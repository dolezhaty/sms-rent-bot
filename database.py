import logging
from typing import List, Optional, Union, Dict, Any
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, update, delete, insert, desc
from sqlalchemy.exc import IntegrityError

from src.config import DIR
from src.database_models import Base, User, Category, Subcategory, Item, ItemData, Sale, SoldItem, Payment, Topup, Order, ReferralHistory
from bin.strings import get_now_date

# # # Реферальная система # # #

async def add_referral_history(referrer_id, referral_id, amount_topup, amount_bonus):
    async with async_session() as session:
        from bin.strings import get_now_date
        new_record = ReferralHistory(
            referrer_id=referrer_id,
            referral_id=referral_id,
            amount_topup=amount_topup,
            amount_bonus=amount_bonus,
            date=get_now_date()
        )
        session.add(new_record)
        await session.commit()

async def get_referral_stats(user_id):
    async with async_session() as session:
        from sqlalchemy import func
        # Считаем количество приглашенных (у которых inviting == user_id)
        result_count = await session.execute(
            select(func.count(User.user_id)).where(User.inviting == user_id)
        )
        count = result_count.scalar() or 0
        
        # Считаем суммарный заработок из ReferralHistory
        result_earnings = await session.execute(
            select(func.sum(ReferralHistory.amount_bonus)).where(ReferralHistory.referrer_id == user_id)
        )
        earnings = result_earnings.scalar() or 0.0
        
        return count, earnings

# # # Логи действий # # #

async def add_action_log(user_id: int, username: str, action_type: str, details: str):
    """Запись действия пользователя в логи"""
    async with async_session() as session:
        from bin.strings import get_now_date
        from src.database_models import ActionLog
        
        new_log = ActionLog(
            user_id=user_id,
            username=username,
            action_type=action_type,
            details=details,
            timestamp=get_now_date()
        )
        session.add(new_log)
        await session.commit()

async def get_action_logs(limit: int = 50):
    """Получение последних логов действий"""
    async with async_session() as session:
        from src.database_models import ActionLog
        result = await session.execute(
            select(ActionLog).order_by(desc(ActionLog.id)).limit(limit)
        )
        return result.scalars().all()

# Настройка БД
DATABASE_URL = f"sqlite+aiosqlite:///{DIR}/shopDB.sqlite"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def create_tables():
    """Создание таблиц (если их нет)"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# # # Пользователи # # #

async def add_user(user_id, username, first_name, last_name, inviting):
    async with async_session() as session:
        try:
            result = await session.execute(select(User).where(User.user_id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                from datetime import datetime
                now = datetime.now()
                reg_date = now.strftime("%d.%m.%Y")
                reg_time = now.strftime("%H:%M:%S")
                
                new_user = User(
                    user_id=user_id,
                    username=username,
                    firstName=first_name,
                    lastName=last_name,
                    inviting=inviting,
                    regDate=reg_date,
                    regTime=reg_time,
                    balance=0.0
                )
                session.add(new_user)
                await session.commit()
                return True
            else:
                # Если пользователь уже есть, просто обновляем его данные
                # Используем values напрямую для избежания лишнего коммита через update_user
                user.username = username
                user.firstName = first_name
                user.lastName = last_name
                await session.commit()
                return False
        except IntegrityError:
            await session.rollback()
            # Если возникла гонка условий (пользователь добавился параллельно)
            # просто попробуем обновить данные существующего
            try:
                stmt = update(User).where(User.user_id == user_id).values(
                    username=username,
                    firstName=first_name,
                    lastName=last_name
                )
                await session.execute(stmt)
                await session.commit()
            except Exception as e:
                logging.error(f"Error in add_user IntegrityError fallback: {e}")
            return False
        except Exception as e:
            await session.rollback()
            logging.error(f"Unexpected error in add_user: {e}")
            return False

async def get_user(user_id_or_username) -> Optional[User]:
    async with async_session() as session:
        if str(user_id_or_username).startswith("@"):
            username = str(user_id_or_username).replace("@", "")
            result = await session.execute(select(User).where(User.username == username))
        else:
            result = await session.execute(select(User).where(User.user_id == int(user_id_or_username)))
        
        user = result.scalar_one_or_none()
        # Для совместимости со старым кодом, который ожидает индексацию (user[1]),
        # нам нужно будет обновить вызывающий код. 
        # Здесь мы возвращаем объект User.
        return user

async def generate_api_key(user_id: int) -> str:
    import hashlib
    from src.config import SECRET_KEY
    from datetime import datetime
    
    # Генерируем уникальный ключ на основе user_id, секрета и текущего времени
    raw_key = f"{user_id}:{SECRET_KEY}:{datetime.now().timestamp()}"
    api_key = "sk_live_" + hashlib.sha256(raw_key.encode()).hexdigest()[:32]
    
    async with async_session() as session:
        stmt = update(User).where(User.user_id == user_id).values(api_key=api_key)
        await session.execute(stmt)
        await session.commit()
    
    return api_key

async def get_user_by_api_key(api_key: str) -> Optional[User]:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.api_key == api_key))
        return result.scalar_one_or_none()

async def get_daily_users(date):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.regDate.like(f"%{date}%")))
        return result.scalars().all()

async def update_user(user_id, username, first_name, last_name):
    async with async_session() as session:
        stmt = update(User).where(User.user_id == user_id).values(
            username=username,
            firstName=first_name,
            lastName=last_name
        )
        await session.execute(stmt)
        await session.commit()

async def set_user_balance(user_id, amount):
    async with async_session() as session:
        stmt = update(User).where(User.user_id == user_id).values(balance=amount)
        await session.execute(stmt)
        await session.commit()

async def update_user_balance(user_id, amount):
    """Атомарное обновление баланса (прибавление/вычитание)"""
    async with async_session() as session:
        stmt = update(User).where(User.user_id == user_id).values(balance=User.balance + amount)
        await session.execute(stmt)
        await session.commit()

async def get_user_balance(user_id):
    async with async_session() as session:
        result = await session.execute(select(User.balance).where(User.user_id == user_id))
        return result.scalar() or 0.0

async def get_all_users():
    async with async_session() as session:
        result = await session.execute(select(User))
        return result.scalars().all()

# # # Покупка товара # # #

async def add_buy(purchase_data):
    async with async_session() as session:
        new_sale = Sale(
            user_id=purchase_data['user_id'],
            item_name=purchase_data['item_name'],
            amount=purchase_data['amount'],
            count=purchase_data['count'],
            date=purchase_data['date'],
            cheque=purchase_data['cheque']
        )
        session.add(new_sale)
        await session.commit()
        
        # Получаем ID только что созданной записи
        # В SQLite autoincrement работает, но чтобы получить ID, нужно рефрешнуть или запросить
        # await session.refresh(new_sale) - работает если объект привязан
        # Но session закрывается.
        # Проще запросить по чеку, как было раньше
        result = await session.execute(select(Sale.id).where(Sale.cheque == purchase_data['cheque']))
        return result.scalar_one()

async def delete_buy_by_cheque(cheque):
    async with async_session() as session:
        await session.execute(delete(Sale).where(Sale.cheque == str(cheque)))
        await session.commit()

async def add_sold_item_data(sale_id, item_data):
    async with async_session() as session:
        # item_data - это список объектов ItemData (или кортежей из старого кода)
        # Старый код: list of tuples/lists. new code: list of ItemData objects?
        # В register_purchase.py: items_data = database.get_item_data(...)
        
        # Если item_data это список строк или объектов
        for item in item_data:
            # item - это объект ItemData (если мы обновили get_item_data)
            # или кортеж (id, item_id, data)
            data_str = item.data if hasattr(item, 'data') else item[2]
            
            new_sold = SoldItem(sale_id=sale_id, item_data=data_str)
            session.add(new_sold)
        await session.commit()

async def get_user_buy(user_id):
    async with async_session() as session:
        result = await session.execute(select(Sale).where(Sale.user_id == user_id))
        return result.scalars().all()

async def get_all_sales():
    async with async_session() as session:
        result = await session.execute(select(Sale))
        return result.scalars().all()

async def get_daily_sales(date):
    async with async_session() as session:
        result = await session.execute(select(Sale).where(Sale.date.like(f"%{date}%")))
        return result.scalars().all()

# # # Категории # # #

async def get_categories():
    async with async_session() as session:
        result = await session.execute(select(Category))
        return result.scalars().all()

async def get_category(category_id):
    async with async_session() as session:
        result = await session.execute(select(Category).where(Category.id == category_id))
        return result.scalar_one_or_none()

async def get_subcategories(category_id):
    async with async_session() as session:
        result = await session.execute(select(Subcategory).where(Subcategory.category_id == category_id))
        return result.scalars().all()

async def get_all_subcategories():
    async with async_session() as session:
        result = await session.execute(select(Subcategory))
        return result.scalars().all()

async def add_category(category_name):
    async with async_session() as session:
        new_cat = Category(name=category_name)
        session.add(new_cat)
        await session.commit()

async def add_subcategory(category_name, category_id):
    async with async_session() as session:
        new_sub = Subcategory(name=category_name, category_id=category_id)
        session.add(new_sub)
        await session.commit()

async def delete_category(category_id):
    async with async_session() as session:
        # Удаление каскадное настроено в моделях, но лучше явно
        # Удаляем товары
        await session.execute(delete(Item).where(Item.category == category_id))
        # Удаляем подкатегории
        await session.execute(delete(Subcategory).where(Subcategory.category_id == category_id))
        # Удаляем категорию
        await session.execute(delete(Category).where(Category.id == category_id))
        await session.commit()

async def delete_subcategory(subcategory_id):
    async with async_session() as session:
        await session.execute(delete(Item).where(Item.subcategory == subcategory_id))
        await session.execute(delete(Subcategory).where(Subcategory.id == subcategory_id))
        await session.commit()

# # # Товары # # #

async def get_items_category(category_id, subcategory_id):
    async with async_session() as session:
        result = await session.execute(
            select(Item).where(Item.category == category_id, Item.subcategory == subcategory_id)
        )
        return result.scalars().all()

async def get_item(item_id):
    async with async_session() as session:
        result = await session.execute(select(Item).where(Item.id == item_id))
        return result.scalar_one_or_none()

async def get_item_count(item_id):
    async with async_session() as session:
        # Считаем количество записей в ItemData для этого item_id
        result = await session.execute(select(ItemData).where(ItemData.item_id == item_id))
        return len(result.scalars().all()) # Не супер эффективно, но работает

async def add_item(item_dict):
    async with async_session() as session:
        new_item = Item(
            name=item_dict["name"],
            desc=item_dict["desc"],
            pic=item_dict["pic"],
            price=item_dict["price"],
            category=item_dict["category"],
            subcategory=item_dict["subcategory"]
        )
        session.add(new_item)
        await session.commit()
        
        # Возвращаем созданный item
        # Нужно получить ID.
        result = await session.execute(select(Item).where(Item.name == item_dict["name"]))
        return result.scalars().first() # Может быть несколько с одним именем, берем первый попавшийся (как в старом коде)

async def delete_item(item_id):
    async with async_session() as session:
        await delete_all_item_data(item_id, session) # Передаем сессию
        await session.execute(delete(Item).where(Item.id == item_id))
        await session.commit()

# # # Позиции товара (ItemData) # # #

async def add_item_data(item, item_data_str):
    async with async_session() as session:
        # item - это объект Item или словарь? В старом коде: item["id"]
        item_id = item.id if hasattr(item, 'id') else item['id']
        
        new_data = ItemData(item_id=item_id, data=item_data_str)
        session.add(new_data)
        await session.commit()

async def get_item_data(item_id, count, if_delete):
    async with async_session() as session:
        # Берем N записей
        result = await session.execute(select(ItemData).where(ItemData.item_id == item_id).limit(count))
        items = result.scalars().all()
        
        if if_delete:
            for item in items:
                await session.delete(item)
            await session.commit()
            
        return items

async def delete_all_item_data(item_id, session=None):
    if session:
        await session.execute(delete(ItemData).where(ItemData.item_id == item_id))
    else:
        async with async_session() as s:
            await s.execute(delete(ItemData).where(ItemData.item_id == item_id))
            await s.commit()

async def get_all_item_data(item_id):
    async with async_session() as session:
        result = await session.execute(select(ItemData).where(ItemData.item_id == item_id))
        return result.scalars().all()

async def get_data(data_id):
    async with async_session() as session:
        result = await session.execute(select(ItemData).where(ItemData.id == data_id))
        return result.scalar_one_or_none()

async def update_item_data(data_id, new_data):
    async with async_session() as session:
        stmt = update(ItemData).where(ItemData.id == data_id).values(data=new_data)
        await session.execute(stmt)
        await session.commit()

async def delete_item_data(data_id):
    async with async_session() as session:
        await session.execute(delete(ItemData).where(ItemData.id == data_id))
        await session.commit()

async def edit_item_param(item_id, param_name, param_value):
    async with async_session() as session:
        # Динамическое обновление поля - опасно в ORM, но реализуемо
        # update(Item).where...values(**{param_name: param_value})
        stmt = update(Item).where(Item.id == item_id).values(**{param_name: param_value})
        await session.execute(stmt)
        await session.commit()

# # # Платежи и пополнения # # #

async def save_payment_data(user_id, invoice_id, item_id, item_name, count, amount, date, message_id=None, chat_id=None):
    async with async_session() as session:
        new_payment = Payment(
            user_id=user_id,
            invoice_id=str(invoice_id),
            item_id=item_id,
            item_name=item_name,
            count=count,
            amount=amount,
            date=date,
            status='pending',
            message_id=message_id,
            chat_id=chat_id
        )
        session.add(new_payment)
        await session.commit()
        return new_payment.id

async def get_last_payment(user_id):
    async with async_session() as session:
        result = await session.execute(
            select(Payment).where(Payment.user_id == user_id).order_by(desc(Payment.id)).limit(1)
        )
        payment = result.scalar_one_or_none()
        
        if payment:
            return {
                'invoice_id': payment.invoice_id,
                'purchase_data': {
                    'user_id': payment.user_id,
                    'item_id': payment.item_id,
                    'item_name': payment.item_name,
                    'count': payment.count,
                    'amount': payment.amount,
                    'date': payment.date
                }
            }
        return None

async def add_topup(user_id, invoice_id, amount_usd, amount_rub):
    async with async_session() as session:
        from datetime import datetime
        date = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        
        # Проверка существования
        existing = await session.execute(select(Topup).where(Topup.invoice_id == str(invoice_id)))
        if existing.scalar_one_or_none():
            return False

        new_topup = Topup(
            user_id=user_id,
            invoice_id=str(invoice_id),
            amount_usd=amount_usd,
            amount_rub=amount_rub,
            date=date
        )
        session.add(new_topup)
        await session.commit()
        return True

async def check_topup_exists(invoice_id):
    async with async_session() as session:
        result = await session.execute(select(Topup).where(Topup.invoice_id == str(invoice_id)))
        return result.scalar_one_or_none() is not None

async def update_payment_status(invoice_id, status):
    async with async_session() as session:
        stmt = update(Payment).where(Payment.invoice_id == str(invoice_id)).values(status=status)
        await session.execute(stmt)
        await session.commit()

async def get_payment_by_invoice(invoice_id):
    async with async_session() as session:
        result = await session.execute(select(Payment).where(Payment.invoice_id == str(invoice_id)))
        payment = result.scalar_one_or_none()
        if payment:
            return {
                'user_id': payment.user_id,
                'amount': payment.amount,
                'status': payment.status,
                'item_id': payment.item_id,
                'item_name': payment.item_name,
                'count': payment.count,
                'date': payment.date,
                'message_id': payment.message_id,
                'chat_id': payment.chat_id
            }
        return None

async def get_all_topups():
    async with async_session() as session:
        result = await session.execute(select(Topup).order_by(Topup.id.desc()))
        return result.scalars().all()

# # # Заказы (Orders) # # #

async def add_order(user_id, order_id, service, country, operator, phone, price, message_id=None, chat_id=None):
    async with async_session() as session:
        import time
        now = time.time()
        expires = now + 900 # 15 minutes
        
        new_order = Order(
            user_id=user_id,
            order_id=str(order_id),
            service=service,
            country=country,
            operator=operator,
            phone=phone,
            price=price,
            status='PENDING',
            created_at=now,
            expires_at=expires,
            message_id=message_id,
            chat_id=chat_id
        )
        session.add(new_order)
        await session.commit()

async def get_active_orders():
    async with async_session() as session:
        result = await session.execute(select(Order).where(Order.status == 'PENDING'))
        return result.scalars().all()

async def get_order(order_id):
    async with async_session() as session:
        result = await session.execute(select(Order).where(Order.order_id == str(order_id)))
        return result.scalar_one_or_none()

async def get_all_orders():
    async with async_session() as session:
        result = await session.execute(select(Order).order_by(Order.id.desc()))
        return result.scalars().all()

async def get_orders_by_date(timestamp_start, timestamp_end):
    async with async_session() as session:
        result = await session.execute(
            select(Order).where(Order.created_at >= timestamp_start, Order.created_at <= timestamp_end)
        )
        return result.scalars().all()

async def get_orders_by_user(user_id):
    async with async_session() as session:
        result = await session.execute(select(Order).where(Order.user_id == user_id).order_by(Order.id.desc()))
        return result.scalars().all()

async def get_user_by_id(user_id):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.user_id == user_id))
        return result.scalar_one_or_none()

async def update_order_status(order_id, status):
    async with async_session() as session:
        # Atomic update: only update if current status is PENDING (to avoid race conditions)
        stmt = update(Order).where(
            Order.order_id == str(order_id),
            Order.status == 'PENDING'
        ).values(status=status)
        res = await session.execute(stmt)
        await session.commit()
        # res.rowcount gives number of rows updated; if 0 - nothing changed (already processed)
        try:
            return res.rowcount > 0
        except Exception:
            return False

async def add_buy_safe(purchase_data):
    """
    Add Sale only if cheque not already exists. Returns True if added, False if already existed.
    """
    async with async_session() as session:
        try:
            async with session.begin():
                existing = await session.execute(select(Sale).where(Sale.cheque == str(purchase_data['cheque'])))
                if existing.scalar_one_or_none():
                    return False

                new_sale = Sale(
                    user_id=purchase_data['user_id'],
                    item_name=purchase_data['item_name'],
                    amount=purchase_data['amount'],
                    count=purchase_data['count'],
                    date=purchase_data['date'],
                    cheque=purchase_data['cheque']
                )
                session.add(new_sale)
                # flush to DB
                await session.flush()
                # get id
                result = await session.execute(select(Sale.id).where(Sale.cheque == purchase_data['cheque']))
                return result.scalar_one()
        except IntegrityError:
            return False

async def delete_order(order_id):
    async with async_session() as session:
        await session.execute(delete(Order).where(Order.order_id == str(order_id)))
        await session.commit()
