from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import database
from src.database_models import User
from bin.api_5sim import FiveSimAPI
from bin.pricing import get_final_price_usd

api_router = APIRouter(prefix="/api/v1", tags=["Public API"])

async def get_user_by_api_key(x_api_key: str = Header(..., description="Your unique API key")) -> User:
    """Dependency to validate API key and return the user."""
    user = await database.get_user_by_api_key(x_api_key)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return user


@api_router.get("/balance", summary="Get user balance")
async def get_balance(user: User = Depends(get_user_by_api_key)):
    """
    Returns the current balance of the user in USD.
    """
    return {
        "user_id": user.user_id,
        "balance_usd": round(user.balance, 4)
    }


@api_router.get("/services", summary="Get list of all available services")
async def get_services(user: User = Depends(get_user_by_api_key)):
    """
    Returns a list of all available service codes (e.g. 'tg', 'wa', 'vk').
    Use these codes in /prices and /buy endpoints.
    """
    prices_data = await FiveSimAPI.get_prices()
    if not prices_data:
        raise HTTPException(status_code=503, detail="Failed to fetch services from provider")

    services = sorted(prices_data.keys())
    return {
        "count": len(services),
        "services": services
    }


@api_router.get("/countries", summary="Get list of countries for a service")
async def get_countries(
    service: str = Query(..., description="Service code (e.g., 'tg', 'wa')"),
    user: User = Depends(get_user_by_api_key)
):
    """
    Returns a list of available countries for the given service,
    along with operator count and cheapest price in USD.
    """
    prices_data = await FiveSimAPI.get_prices(product=service)
    if not prices_data or service not in prices_data:
        raise HTTPException(status_code=404, detail=f"No data found for service '{service}'")

    countries_data = prices_data[service]
    result = {}

    for country, operators in countries_data.items():
        available_operators = {}
        for operator, info in operators.items():
            cost_rub = info.get('cost')
            count = info.get('count')
            if count and count > 0 and cost_rub:
                available_operators[operator] = {
                    "price_usd": get_final_price_usd(float(cost_rub)),
                    "count": count
                }
        if available_operators:
            cheapest = min(available_operators.values(), key=lambda x: x["price_usd"])
            result[country] = {
                "min_price_usd": cheapest["price_usd"],
                "operators_available": len(available_operators)
            }

    return {
        "service": service,
        "countries_count": len(result),
        "countries": result
    }


@api_router.get("/prices", summary="Get prices for a service in a country")
async def get_prices(
    country: str = Query(..., description="Country code (e.g., 'russia', 'england')"),
    service: str = Query(..., description="Service code (e.g., 'tg', 'wa', 'other')"),
    user: User = Depends(get_user_by_api_key)
):
    """
    Returns available operators, stock count, and prices (in USD) for a specific country and service.
    Prices already include the platform's markup.
    """
    prices_data = await FiveSimAPI.get_prices(country=country, product=service)

    if not prices_data or service not in prices_data:
        raise HTTPException(status_code=404, detail=f"No numbers available for service '{service}' in '{country}'")

    operators_data = prices_data[service]
    result = {}

    for operator, info in operators_data.items():
        cost_rub = info.get('cost')
        count = info.get('count')

        if count and count > 0 and cost_rub:
            final_price_usd = get_final_price_usd(float(cost_rub))
            result[operator] = {
                "price_usd": final_price_usd,
                "count": count
            }

    if not result:
        raise HTTPException(status_code=404, detail=f"No numbers in stock for service '{service}' in '{country}'")

    return {
        "country": country,
        "service": service,
        "operators": result
    }


class BuyRequest(BaseModel):
    country: str
    service: str
    operator: str
    max_price_usd: float


@api_router.post("/buy", summary="Buy a number")
async def buy_number(request: BuyRequest, user: User = Depends(get_user_by_api_key)):
    """
    Purchases a phone number for the specified country, service, and operator.
    Deducts the cost from the user's balance.
    """
    # 1. Check price and stock
    prices_data = await FiveSimAPI.get_prices(country=request.country, product=request.service)

    if not prices_data or request.service not in prices_data:
        raise HTTPException(status_code=404, detail="Number not available right now")

    operators_data = prices_data[request.service]

    # Если operator == "any" — выбираем самого дешёвого с наличием
    if request.operator.lower() == "any":
        best_op = None
        best_cost = None
        for op_name, op_info in operators_data.items():
            c = op_info.get('cost')
            cnt = op_info.get('count')
            if c and cnt and cnt > 0:
                if best_cost is None or float(c) < best_cost:
                    best_cost = float(c)
                    best_op = op_name
        if not best_op:
            raise HTTPException(status_code=404, detail="Number not available right now")
        actual_operator = best_op
        operator_info = operators_data[best_op]
    else:
        if request.operator not in operators_data:
            raise HTTPException(status_code=404, detail="Number not available right now")
        actual_operator = request.operator
        operator_info = operators_data[request.operator]

    cost_rub = operator_info.get('cost')
    count = operator_info.get('count')

    if not count or count <= 0:
        raise HTTPException(status_code=404, detail="Number out of stock")

    # Проверяем кастомную цену для этого юзера
    custom_price = await database.get_custom_price(user.user_id, request.service, request.country)
    if custom_price is not None:
        final_price_usd = round(custom_price, 4)
    else:
        final_price_usd = get_final_price_usd(float(cost_rub))

    if final_price_usd > request.max_price_usd:
        raise HTTPException(status_code=400, detail=f"Price ({final_price_usd}) exceeds max_price_usd ({request.max_price_usd})")

    if user.balance < final_price_usd:
        raise HTTPException(status_code=402, detail="Insufficient funds")

    # 2. Buy from 5sim
    buy_result = await FiveSimAPI.buy_number(country=request.country, operator=actual_operator, product=request.service)

    if not buy_result or 'id' not in buy_result:
        raise HTTPException(status_code=500, detail="Failed to purchase number from provider")

    order_id = str(buy_result['id'])
    phone = buy_result.get('phone')

    # 3. Deduct balance and save order
    await database.update_user_balance(user.user_id, -final_price_usd)  # fix: was update_balance
    await database.add_order(
        user_id=user.user_id,
        order_id=order_id,
        service=request.service,
        country=request.country,
        operator=request.operator,
        price=final_price_usd,
        phone=phone
    )

    return {
        "order_id": order_id,
        "phone": phone,
        "price_usd": final_price_usd,
        "status": "PENDING"
    }


@api_router.get("/orders", summary="Get user's orders")
async def get_orders(
    status: Optional[str] = Query(None, description="Filter by status: PENDING, FINISHED, CANCELED"),
    user: User = Depends(get_user_by_api_key)
):
    """
    Returns list of all orders for the authenticated user.
    Optionally filter by status.
    """
    orders = await database.get_orders_by_user(user.user_id)

    if status:
        orders = [o for o in orders if o.status == status.upper()]

    result = []
    for o in orders:
        result.append({
            "order_id": o.order_id,
            "service": o.service,
            "country": o.country,
            "operator": o.operator,
            "phone": o.phone,
            "price_usd": o.price,
            "status": o.status,
            "sms_code": o.sms_code if hasattr(o, 'sms_code') else None,
            "created_at": o.created_at,
            "expires_at": o.expires_at
        })

    return {
        "count": len(result),
        "orders": result
    }


@api_router.get("/check/{order_id}", summary="Check SMS status")
async def check_sms(order_id: str, user: User = Depends(get_user_by_api_key)):
    """
    Checks the status of an active order and returns the SMS code if received.
    """
    order = await database.get_order(order_id)
    if not order or order.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Order not found")

    sms_code = order.sms_code if hasattr(order, 'sms_code') else None

    if order.status != "PENDING":
        return {
            "order_id": order_id,
            "status": order.status,
            "sms_code": sms_code
        }

    # Check with provider
    check_result = await FiveSimAPI.check_order(order_id)
    if not check_result:
        raise HTTPException(status_code=500, detail="Failed to check order status")

    status = check_result.get('status')
    sms_array = check_result.get('sms', [])

    sms_code = None
    if sms_array:
        sms_code = sms_array[0].get('code')

    if status == 'FINISHED' or sms_code:
        await database.update_order_status(order_id, 'FINISHED')
        return {
            "order_id": order_id,
            "status": "FINISHED",
            "sms_code": sms_code
        }

    if status in ('CANCELED', 'TIMEOUT'):
        await database.update_user_balance(user.user_id, order.price)  # fix: was update_balance
        await database.update_order_status(order_id, 'CANCELED')
        return {
            "order_id": order_id,
            "status": "CANCELED",
            "sms_code": None
        }

    return {
        "order_id": order_id,
        "status": "PENDING",
        "sms_code": None
    }


@api_router.post("/cancel/{order_id}", summary="Cancel order")
async def cancel_order(order_id: str, user: User = Depends(get_user_by_api_key)):
    """
    Cancels an active order and refunds the money to the user's balance.
    """
    order = await database.get_order(order_id)
    if not order or order.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Cannot cancel order in status {order.status}")

    await FiveSimAPI.cancel_order(order_id)

    await database.update_user_balance(user.user_id, order.price)  # fix: was update_balance
    await database.update_order_status(order_id, 'CANCELED')

    return {
        "order_id": order_id,
        "status": "CANCELED",
        "refunded_usd": order.price
    }
