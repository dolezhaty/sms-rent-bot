
import math
import logging

logger = logging.getLogger(__name__)

def calculate_dynamic_markup(base_price_usd: float) -> float:
    """
    Рассчитывает финальную цену с учетом динамической наценки (Tiered Pricing).
    
    Логика (на основе цены в USD):
    1. Price < $3: Наценка 100% (x2.0)
    2. $3 <= Price < $5: Наценка 30% (x1.3)
    3. Price >= $5: Наценка 15% (x1.15)
    
    :param base_price_usd: Исходная цена в USD
    :return: Цена с наценкой в USD
    """
    if base_price_usd <= 0:
        return 0.0
        
    price_usd = base_price_usd
    
    if price_usd < 3.0:
        markup = 1.00 # 100%
    elif price_usd < 5.0:
        markup = 0.30 # 30%
    else:
        markup = 0.15 # 15%
        
    final_price = base_price_usd * (1 + markup)
    
    # Округляем до 4 знаков
    return round(final_price, 4)

def get_final_price_usd(base_price_usd: float) -> float:
    """
    Рассчитывает полную цену для пользователя (наценка + комиссия платежки).
    """
    from src.config import CRYPTOBOT_COMMISSION
    
    # 1. Применяем динамическую наценку
    price_with_margin = calculate_dynamic_markup(base_price_usd)
    
    # 2. Добавляем комиссию CryptoBot (3%)
    # Формула: X = price_with_margin / (1 - commission)
    final_usd = price_with_margin / (1 - CRYPTOBOT_COMMISSION)
    
    # 3. Округляем до 2 знаков в большую сторону
    return math.ceil(final_usd * 100) / 100

def test_markup():
    print(f"Testing Markup Logic:")
    # Test cases in USD
    test_cases_usd = [0.1, 1.0, 2.9, 3.0, 4.0, 4.9, 5.0, 10.0]
    
    print(f"{'Base($)':<10} | {'Final($)':<10} | {'Markup %':<10}")
    print("-" * 40)
    
    for usd in test_cases_usd:
        final_usd = calculate_dynamic_markup(usd)
        markup_pct = ((final_usd / usd) - 1) * 100
        print(f"{usd:<10.2f} | {final_usd:<10.2f} | {markup_pct:<10.1f}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    test_markup()
