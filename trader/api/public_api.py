"""
Interface pública da API do Mercado Bitcoin.
Esta interface não requer autenticação e pode ser usada para acessar dados públicos como preços.
"""

import logging
from typing import Any, Dict, List

import requests

from ..models.public_data import TickerData


class MercadoBitcoinPublicAPI:
    """
    Interface pública da API do Mercado Bitcoin.
    Não requer autenticação - ideal para bots que só precisam de dados de preços.
    """

    def __init__(self):
        self.base_url = "https://api.mercadobitcoin.net/api/v4"
        self.session = requests.Session()
        self.logger = logging.getLogger(__name__)

        # Headers padrão para requisições públicas
        self.session.headers.update(
            {
                "Content-Type": "application/json",
            }
        )

    def _make_public_request(
        self, method: str, endpoint: str, params: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """Faz requisição pública para a API (sem autenticação)"""
        url = f"{self.base_url}{endpoint}"

        response = self.session.request(method, url, params=params)

        if response.status_code != 200:
            raise Exception(
                f"Erro na requisição {url}: status={response.status_code} response={response.text}"
            )

        return response.json()

    def get_ticker(self, symbol: str) -> TickerData:
        """
        Obtém ticker de um par específico.

        Args:
            symbol: Símbolo do par (ex: 'BTC-BRL')

        Returns:
            TickerData: Dados do ticker
        """
        response = self._make_public_request(
            "GET", "/tickers", params={"symbols": symbol}
        )
        ticker_list = [TickerData.from_dict(ticker) for ticker in response]
        return ticker_list[0] if ticker_list else None

    def get_all_tickers(self) -> List[TickerData]:
        """
        Obtém todos os tickers disponíveis.

        Returns:
            List[TickerData]: Lista com todos os tickers
        """
        response = self._make_public_request("GET", "/tickers")
        return [TickerData.from_dict(ticker) for ticker in response]
