"""
Interface privada da API do Mercado Bitcoin.
Esta interface requer autenticação e pode ser usada para acessar dados de conta e realizar operações.
"""

import json
import logging
from typing import Any

import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..models.account_data import AccountBalanceData, AccountData
from .base_api import PrivateAPIBase


class UnauthorizedError(Exception):
    """Exceção para erros de autenticação (401)"""

    pass


class MercadoBitcoinPrivateAPIBase(PrivateAPIBase):
    """
    Interface abstrata da API privada do Mercado Bitcoin.
    Herda de PrivateAPIBase para manter compatibilidade.
    """

    pass


class MercadoBitcoinPrivateAPI(MercadoBitcoinPrivateAPIBase):
    """
    Interface privada da API do Mercado Bitcoin.
    Requer autenticação - ideal para operações que precisam de acesso à conta.
    """

    def __init__(self, api_key: str, api_secret: str):
        self.base_url = "https://api.mercadobitcoin.net/api/v4"
        self.session = requests.Session()
        self.api_key = api_key
        self.api_secret = api_secret
        self.logger = logging.getLogger(__name__)
        self._authorize()

    def _authorize(self):
        """Realiza autenticação na API"""
        endpoint = "/authorize"
        url = f"{self.base_url}{endpoint}"

        headers = {
            "Content-Type": "application/json",
        }

        body = json.dumps({"login": self.api_key, "password": self.api_secret})
        response = self.session.request("POST", url, headers=headers, data=body)

        if response.status_code != 200:
            raise Exception(
                f"Erro na requisição {url}: status={response.status_code} response={response.text}. {body=}"
            )

        json_response = response.json()
        access_token = json_response["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {access_token}"})
        self.logger.info("Autenticação realizada com sucesso")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(UnauthorizedError),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
        reraise=True,
    )
    def _make_authenticated_request(
        self, method: str, endpoint: str, data: dict | None = None
    ) -> Any:
        """Faz requisição autenticada para a API com retry automático em caso de 401"""
        url = f"{self.base_url}{endpoint}"
        body = json.dumps(data) if data else ""

        headers = {
            "Content-Type": "application/json",
        }
        response = self.session.request(method, url, headers=headers, data=body)

        if response.status_code == 401:
            self.logger.warning("Token expirado, re-autenticando...")
            self._authorize()
            raise UnauthorizedError("Token expirado, re-autenticação realizada")

        if response.status_code != 200:
            raise Exception(
                f"Erro na requisição {url}: status={response.status_code} response={response.text}. {body=}"
            )

        return response.json()

    def get_accounts(self) -> list[AccountData]:
        """Obtém lista de contas"""
        response: list[dict[str, Any]] = self._make_authenticated_request(
            "GET", "/accounts"
        )
        return [AccountData.from_dict(account) for account in response]

    def get_account_balance(self, account_id: str) -> list[AccountBalanceData]:
        """Obtém saldo da conta"""
        response = self._make_authenticated_request(
            "GET", f"/accounts/{account_id}/balances"
        )
        return [AccountBalanceData.from_dict(balance) for balance in response]

    def place_order(
        self, account_id: str, symbol: str, side: str, type_order: str, quantity: str
    ) -> str:
        data = {
            "qty": quantity,
            "side": side,
            "type": type_order,
        }
        response = self._make_authenticated_request(
            "POST", f"/accounts/{account_id}/{symbol}/orders", data
        )
        return response["orderId"]

    def get_orders(
        self, symbol: str | None = None, status: str | None = None
    ) -> dict[str, Any]:
        """lista ordens"""
        endpoint = "/orders"
        params = []
        if symbol:
            params.append(f"symbol={symbol}")
        if status:
            params.append(f"status={status}")
        if params:
            endpoint += "?" + "&".join(params)

        return self._make_authenticated_request("GET", endpoint)
