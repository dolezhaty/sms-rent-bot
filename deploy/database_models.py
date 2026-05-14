from sqlalchemy import Column, Integer, String, Float, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = 'UserList'
    
    # В текущей БД user_id не является Primary Key, но уникален.
    # SQLAlchemy требует PK. Будем считать user_id первичным ключом.
    user_id = Column(Integer, primary_key=True) 
    username = Column(String)
    firstName = Column(String)
    lastName = Column(String)
    balance = Column(Float, default=0.0)
    inviting = Column(Integer)
    regDate = Column(String)
    regTime = Column(String)
    api_key = Column(String)

class Category(Base):
    __tablename__ = 'Category'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    
    subcategories = relationship("Subcategory", back_populates="category", cascade="all, delete-orphan")
    items = relationship("Item", back_populates="category_rel", cascade="all, delete-orphan")

class Subcategory(Base):
    __tablename__ = 'Subcategory'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    category_id = Column(Integer, ForeignKey('Category.id'))
    
    category = relationship("Category", back_populates="subcategories")
    items = relationship("Item", back_populates="subcategory_rel", cascade="all, delete-orphan")

class Item(Base):
    __tablename__ = 'ItemList'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    desc = Column(Text)
    pic = Column(String)
    price = Column(Integer) # В БД это INT, хотя цены могут быть дробными. Пока оставим как есть, но это проблема.
    category = Column(Integer, ForeignKey('Category.id'))
    subcategory = Column(Integer, ForeignKey('Subcategory.id'))
    
    category_rel = relationship("Category", back_populates="items")
    subcategory_rel = relationship("Subcategory", back_populates="items")
    data_items = relationship("ItemData", back_populates="item", cascade="all, delete-orphan")

class ItemData(Base):
    __tablename__ = 'Items'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(Integer, ForeignKey('ItemList.id'))
    data = Column(Text)
    
    item = relationship("Item", back_populates="data_items")

class Sale(Base):
    __tablename__ = 'Sales'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('UserList.user_id'))
    item_name = Column(String)
    amount = Column(Integer) # Тут тоже INT, но мы переходим на USD (Float). 
    # SQLAlchemy при чтении INT вернет int. Если там лежит float (SQLite позволяет), вернет float.
    count = Column(Integer)
    date = Column(String)
    cheque = Column(String)
    
    sold_items = relationship("SoldItem", back_populates="sale", cascade="all, delete-orphan")

class SoldItem(Base):
    __tablename__ = 'SoldItems'
    
    # В оригинале нет ID, только sale_id и data. 
    # SQLAlchemy нужен PK. Используем rowid или добавим фиктивный ID при маппинге?
    # SQLite имеет скрытый rowid.
    # Определим составной PK или просто sale_id, но sale_id не уникален (много товаров в одной продаже).
    # Для простоты добавим id, которого нет в БД, но SQLAlchemy будет ругаться.
    # ВАЖНО: Если таблицы созданы без PK, SQLAlchemy сложно мапить.
    # Попробуем использовать sale_id + item_data как составной ключ, хотя это костыль.
    
    sale_id = Column(Integer, ForeignKey('Sales.id'), primary_key=True)
    item_data = Column(Text, primary_key=True) # Составной ключ
    
    sale = relationship("Sale", back_populates="sold_items")

class Payment(Base):
    __tablename__ = 'PaymentData'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('UserList.user_id'))
    invoice_id = Column(String)
    item_id = Column(Integer)
    item_name = Column(String)
    count = Column(Integer)
    amount = Column(Integer)
    date = Column(String)
    status = Column(String, default='pending')
    message_id = Column(Integer, nullable=True)
    chat_id = Column(Integer, nullable=True)

class ActionLog(Base):
    __tablename__ = 'ActionLogs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer)
    username = Column(String)
    action_type = Column(String) # topup, purchase, sms_received
    details = Column(String)
    timestamp = Column(String) # "YYYY-MM-DD HH:MM:SS"

class Topup(Base):
    __tablename__ = 'Topups'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer)
    invoice_id = Column(String, unique=True)
    amount_usd = Column(Float)
    amount_rub = Column(Float)
    date = Column(String)

class ReferralHistory(Base):
    __tablename__ = 'ReferralHistory'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    referrer_id = Column(Integer, ForeignKey('UserList.user_id'))
    referral_id = Column(Integer, ForeignKey('UserList.user_id'))
    amount_topup = Column(Float)
    amount_bonus = Column(Float)
    date = Column(String)

class UserPricing(Base):
    __tablename__ = 'UserPricing'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('UserList.user_id'))
    service = Column(String)   # e.g. 'wallapop'
    country = Column(String)   # e.g. 'spain', или '*' = все страны
    price_usd = Column(Float)  # кастомная цена

class Order(Base):
    __tablename__ = 'Orders'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('UserList.user_id'))
    order_id = Column(String, unique=True) # ID заказа в 5sim
    service = Column(String)
    country = Column(String)
    operator = Column(String)
    phone = Column(String)
    price = Column(Float) # Цена с наценкой
    status = Column(String) # pending, finished, cancelled, expired
    created_at = Column(Float) # Timestamp
    expires_at = Column(Float) # Timestamp + 15 min
    message_id = Column(Integer, nullable=True) # ID сообщения для обновления
    chat_id = Column(Integer, nullable=True) # ID чата
