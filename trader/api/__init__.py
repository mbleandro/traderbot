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
