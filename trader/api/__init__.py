"""
Módulo de interfaces da API do Mercado Bitcoin.
"""

from abc import ABC, abstractmethod
from typing import Any

from trader.models.account_data import AccountBalanceData, AccountData

from .fake_private_api import FakeMercadoBitcoinPrivateAPI
from .private_api import MercadoBitcoinPrivateAPI, UnauthorizedError
from .public_api import MercadoBitcoinPublicAPI

__all__ = [
    "MercadoBitcoinPublicAPI",
    "MercadoBitcoinPrivateAPI",
    "FakeMercadoBitcoinPrivateAPI",
    "UnauthorizedError",
]


class MercadoBitcoinPrivateAPIBase(ABC):
    """
    Interface abstrata da API privada do Mercado Bitcoin.
    """

    @abstractmethod
    def get_accounts(self) -> list[AccountData]:
        """Obtém lista de contas"""
        ...

    @abstractmethod
    def get_account_balance(self, account_id: str) -> list[AccountBalanceData]:
        """Obtém saldo da conta"""
        ...

    @abstractmethod
    def place_order(
        self, account_id: str, symbol: str, side: str, type_order: str, quantity: str
    ) -> str:
        """Coloca uma ordem de compra/venda"""
        ...

    @abstractmethod
    def get_orders(
        self, symbol: str | None = None, status: str | None = None
    ) -> dict[str, Any]:
        """Lista ordens"""
        ...
