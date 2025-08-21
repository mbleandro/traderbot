"""
Interface falsa da API privada do Mercado Bitcoin para testes.
Esta classe simula o comportamento da API real sem fazer requisições HTTP.
"""

import logging
from typing import Any, List

from trader.api.private_api import MercadoBitcoinPrivateAPIBase

from ..models.account_data import AccountBalanceData, AccountData


class FakeMercadoBitcoinPrivateAPI(MercadoBitcoinPrivateAPIBase):
    """
    Interface falsa da API privada do Mercado Bitcoin para testes.
    Simula o comportamento da API real sem fazer requisições HTTP reais.
    """

    def __init__(self, api_key: str = "fake_key", api_secret: str = "fake_secret"):
        self.logger = logging.getLogger(__name__)
        self._order_counter = 0

        # Dados fake para simulação
        self._fake_accounts = [
            {
                "currency": "BRL",
                "currencySign": "R$",
                "id": "fake_account_1",
                "name": "Conta Principal",
                "type": "exchange",
            }
        ]

        self._fake_balances = {
            "fake_account_1": [
                {
                    "available": "10000.00",
                    "on_hold": "0.00",
                    "symbol": "BRL",
                    "total": "10000.00",
                },
                {
                    "available": "0.5",
                    "on_hold": "0.1",
                    "symbol": "BTC",
                    "total": "0.0120000",
                },
            ],
        }

        self._fake_orders: list[dict[str, str]] = []

    def get_accounts(self) -> List[AccountData]:
        """Retorna lista de contas fake"""
        return [AccountData.from_dict(account) for account in self._fake_accounts]

    def get_account_balance(self, account_id: str) -> List[AccountBalanceData]:
        """Retorna saldo de uma conta fake"""
        return [
            AccountBalanceData.from_dict(b)
            for b in self._fake_balances.get(account_id, [])
        ]

    def place_order(
        self, account_id: str, symbol: str, side: str, type_order: str, quantity: str
    ) -> str:
        self._order_counter += 1
        order_id = f"fake_order_{self._order_counter}"

        # Adiciona ordem fake à lista
        fake_order = {
            "orderId": order_id,
            "account_id": account_id,
            "symbol": symbol,
            "side": side,
            "type": type_order,
            "quantity": quantity,
            "status": "pending",
        }
        self._fake_orders.append(fake_order)

        self.logger.info(f"Ordem fake criada: {order_id}")
        return order_id

    def get_orders(
        self, symbol: str | None = None, status: str | None = None
    ) -> dict[str, Any]:
        """Retorna lista de ordens fake"""
        return self._fake_orders[0]  # TODO: corrigir tipo do retorno
