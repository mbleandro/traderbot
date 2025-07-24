"""
Dataclasses para dados de conta da API do Mercado Bitcoin.
Estes dados requerem autenticação para serem acessados.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict


@dataclass
class AccountData:
    """Representa os dados de uma conta do Mercado Bitcoin"""

    currency: str
    currencySign: str
    id: str
    name: str
    type: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AccountData":
        """Cria uma instância AccountData a partir de um dicionário"""
        return cls(
            currency=data["currency"],
            currencySign=data["currencySign"],
            id=data["id"],
            name=data["name"],
            type=data["type"],
        )


@dataclass
class AccountBalanceData:
    """Representa os dados de saldo de uma conta do Mercado Bitcoin"""

    available: Decimal
    on_hold: Decimal
    symbol: str
    total: Decimal

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AccountBalanceData":
        """Cria uma instância AccountBalanceData a partir de um dicionário"""
        return cls(
            available=Decimal(data["available"]),
            on_hold=Decimal(data["on_hold"]),
            symbol=data["symbol"],
            total=Decimal(data["total"]),
        )
