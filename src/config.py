import configparser
import os

DIR = os.path.abspath(__file__)[:-14]

config = configparser.ConfigParser()
config.read(f"{DIR}/settings.ini")
TOKEN = config["settings"]["token"]
COMMENT = config["settings"]["comment_pay"]
CRYPTOBOT_TOKEN = config["settings"]["cryptobot_token"]
try:
    XROCKET_TOKEN = config["settings"]["xrocket_token"]
except KeyError:
    XROCKET_TOKEN = ""
    print("Не указан xrocket_token в settings.ini")
try:
    FIVESIM_TOKEN = config["settings"]["fivesim_token"]
except KeyError:
    FIVESIM_TOKEN = ""
    print("Не указан fivesim_token в settings.ini")

ADMIN_USERNAME = config.get("settings", "admin_username", fallback="admin")
ADMIN_PASSWORD = config.get("settings", "admin_password", fallback="admin123")
SECRET_KEY = config.get("settings", "secret_key", fallback="default-secret-key-12345")

# Наценка на товары (в процентах)
# Пример: 30 = +30% к цене
MARGIN_PERCENT = 30

# Комиссия CryptoBot (которую мы перекладываем на пользователя)
# 3% = 0.03
CRYPTOBOT_COMMISSION = 0.03

# Курс доллара больше не нужен, так как мы перешли на USD
# USD_RATE = 96.0


get_id = config["settings"]["admin_id"]
ADMIN_ID = []

if "," in get_id:
    get_id = get_id.split(",")
    for a in get_id:
        ADMIN_ID.append(str(a))
else:
    try:
        ADMIN_ID = [str(get_id)]
    except ValueError:
        ADMIN_ID = [0]
        print("Не указан Admin_ID")


def is_admin(user_id):
    """
    Проверка юзера на админа

    :param user_id: id юзера
    :return: true - юзер админ, false - нет
    """
    return str(user_id) in ADMIN_ID


def create_folder(src):
    """
    Проверка/создание папки с путём src

    :param src: путь к папке
    :return:
    """
    if not os.path.exists(src):
        os.mkdir(src)
