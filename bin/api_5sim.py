from bin.providers import current_provider

# Proxy class for backward compatibility
class FiveSimAPI:
    @staticmethod
    async def get_all_services_list():
        return await current_provider.get_all_services_list()

    @staticmethod
    async def get_user_profile():
        return await current_provider.get_balance()

    @staticmethod
    async def get_prices(country=None, product=None):
        return await current_provider.get_prices(country, product)

    @staticmethod
    async def buy_number(country, operator, product):
        return await current_provider.buy_number(country, operator, product)

    @staticmethod
    async def check_order(order_id):
        return await current_provider.check_order(order_id)

    @staticmethod
    async def finish_order(order_id):
        return await current_provider.finish_order(order_id)

    @staticmethod
    async def cancel_order(order_id):
        return await current_provider.cancel_order(order_id)

    @staticmethod
    async def ban_order(order_id):
        return await current_provider.ban_order(order_id)

    @staticmethod
    async def get_countries_for_service(service):
        return await current_provider.get_countries_for_service(service)

    @staticmethod
    def get_country_flag(country_code):
        return current_provider.get_country_flag(country_code)

