from datetime import datetime

import database
from bin.keyboards import create_list_keyboard


async def get_sort_sales_keyboard(last_index):
    """
    Создание клавиатуры с датами для статистики

    :param last_index: последний индекс для клавиатуры
    :return:
    """
    sales = await database.get_all_sales()
    sales = sales[::-1]
    sales_sort = []
    for sale in sales:
        date_str = sale.date if hasattr(sale, 'date') else sale[5]
        parsed_date = datetime.strptime(date_str.split(" ")[0], "%d/%m/%Y")
        date = parsed_date.strftime("%d/%m/%Y")

        if date not in sales_sort:
            sales_sort.append(date)

    keyboard = create_list_keyboard(data=sales_sort,
                                    last_index=int(last_index),
                                    page_click=f"daily_stat=",
                                    btn_text_param="daily_stat",
                                    btn_click="get_daily")
    return keyboard
