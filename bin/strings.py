import collections
import random
from datetime import datetime

from src.config import COMMENT
from src.const import const_ru


def format_stat(dict_data):
    """
    Форматирование данных для статистики

    :param dict_data: словарь с данными
    :return:
    """
    result = ""
    for key, value in collections.Counter(dict_data).most_common(10):
        result += f"▫ {key} - {value}\n"

    return result


async def item_format(item):
    """
    Создание текста для кнопки с товаром

    :param item: объект из БД с товаром
    :return:
    """
    import database
    return f"{item.name} | ${item.price} | {await database.get_item_count(item.id)} шт."


def create_comment():
    """
    Генерация комментария для оплаты

    :return:
    """
    key_pass = list("1234567890QWERTYUIOPASDFGHJKLZXCVBNMqwertyuiopasdfghjklzxcvbnm")
    random.shuffle(key_pass)
    key_buy = "".join([random.choice(key_pass) for i in range(15)])

    return f"{COMMENT}:{key_buy}"


def get_now_date():
    """
    Получение текущей даты

    :return:
    """
    now_data = datetime.now()

    return now_data.strftime("%d/%m/%Y %H:%M:%S")


def get_cheque_num():
    """
    Генерация номера чека (только цифры)

    :return:
    """
    # Генерируем 10-значный номер из цифр
    return "".join([str(random.randint(0, 9)) for i in range(10)])


async def get_user_link(user_id):
    """
    Получение ссылка на юзера

    :param user_id: id юзера
    :return:
    """
    import database
    user = await database.get_user(str(user_id))
    if user is None:
        return ""

    if user.firstName is None:
        nickname = user.user_id
    else:
        nickname = user.firstName

    return f"<a href='tg://user?id={user.user_id}'>{nickname}</a>"


def get_pay_message(name_buy, payment_form: dict, comment, warning_payment, amount):
    """
    Создание сообщения для оплаты

    :param name_buy: название покупки
    :param payment_form: информация об оплате
    :param comment: комментарий
    :param warning_payment: предупреждение об оплате
    :param amount: стоимость оплаты
    :return:
    """
    pay_info = ""

    if len(payment_form) > 0:
        pay_info = f"💳 Способ оплаты: <b>{payment_form['name']}</b>\n"

        if payment_form['name'] == const_ru['qiwi']:
            pay_info += f"📱 {payment_form['key']}: <b>{payment_form['value']}</b>\n" \
                        f"📋 Комментарий: <b>{comment}</b>\n"

    return f"💳 {name_buy}\n" \
           f"Для оплаты нажмите <b>{const_ru['buy_item']}</b>\n" \
           f"Поля менять <b>не нужно</b>\n" \
           f"{warning_payment}\n" \
           f"После оплаты нажмите <b>{const_ru['check_buy']}</b>\n\n" \
           f"➖➖➖➖➖➖➖➖➖➖\n" \
           f"{pay_info}" \
           f"💵 Сумма оплаты: <b>${amount}</b>\n" \
           f"➖➖➖➖➖➖➖➖➖➖"


async def get_buy_message(user_id, purchase_data, user_mode):
    """
    Получение сообщения о покупке

    :param user_id: id пользователя
    :param purchase_data: данные о покупке
    :param user_mode: true - режим пользователя, false - админ
    :return:
    """
    if user_mode:
        return "🛒 Информация о покупке\n" \
               f"➖➖➖➖➖➖➖➖➖➖\n" \
               f"🆔 Чек: <b>{purchase_data['cheque']}</b>\n" \
               f"➖➖➖➖➖➖➖➖➖➖\n" \
               f"📙 Название товара: <b>{purchase_data['item_name']}</b>\n" \
               f"📦 Количество: <b>{purchase_data['count']} шт.</b>\n" \
               f"💰 Сумма покупки: <b>${purchase_data['amount']}</b>\n" \
               f"➖➖➖➖➖➖➖➖➖➖\n" \
               f"📱 Данные:\n\n"
    else:
        return "🛒 Новая покупка\n" \
               f"➖➖➖➖➖➖➖➖➖➖\n" \
               f"🆔 Чек: <b>{purchase_data['cheque']}</b>\n" \
               f"🙍‍♂ Покупатель: {await get_user_link(user_id)}\n" \
               f"➖➖➖➖➖➖➖➖➖➖\n" \
               f"📙 Название товара: <b>{purchase_data['item_name']}</b>\n" \
               f"📦 Количество: <b>{purchase_data['count']} шт</b>\n" \
               f"💰 Сумма покупки: <b>${purchase_data['amount']}</b>\n" \
               f"➖➖➖➖➖➖➖➖➖➖\n" \
               f"📱 Данные:\n\n"
