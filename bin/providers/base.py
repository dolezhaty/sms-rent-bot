
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

class BaseSMSProvider(ABC):
    """
    Abstract base class for SMS providers (5sim, SMS-Activate, etc.)
    """
    
    @abstractmethod
    async def get_balance(self) -> float:
        """Get account balance"""
        pass

    @abstractmethod
    async def get_prices(self, country: Optional[str] = None, product: Optional[str] = None) -> Dict[str, Any]:
        """
        Get prices for services.
        Should return standardized format:
        {
            "service_name": {
                "operator_name": {"cost": 10.0, "count": 100},
                ...
            }
        }
        """
        pass

    @abstractmethod
    async def buy_number(self, country: str, operator: str, product: str) -> Dict[str, Any]:
        """
        Buy a number.
        Should return:
        {
            "id": "order_id",
            "phone": "+123456789",
            "price": 10.0,
            ...
        }
        """
        pass

    @abstractmethod
    async def check_order(self, order_id: str) -> Dict[str, Any]:
        """Check order status"""
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> Any:
        """Cancel order"""
        pass

    @abstractmethod
    async def finish_order(self, order_id: str) -> Any:
        """Finish order (mark as done)"""
        pass
    
    @abstractmethod
    async def ban_order(self, order_id: str) -> Any:
        """Ban number (mark as bad)"""
        pass
    
    @abstractmethod
    async def get_countries(self) -> Dict[str, Any]:
        """Get list of supported countries"""
        pass
