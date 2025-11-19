"""
Adaptadores para a API Jupiter que implementam as interfaces base.
Permite usar Jupiter com a mesma interface do Mercado Bitcoin.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List

from ..models.account_data import AccountBalanceData, AccountData
from ..models.public_data import Candles, TickerData
from .base_api import PrivateAPIBase, PublicAPIBase
from .jupiter_public_api import SOLANA_TOKENS, JupiterPublicAPI


class JupiterPublicAPIAdapter(PublicAPIBase):
    """
    Adaptador da API pública Jupiter para a interface base.
    Converte chamadas da interface padrão para chamadas específicas da Jupiter.
    """

    def __init__(self, use_pro: bool = False):
        self.jupiter_api = JupiterPublicAPI(use_pro=use_pro)
        self.logger = logging.getLogger(__name__)

        # Cache de tokens para conversão de símbolos
        self._token_cache: dict[str, tuple[str, str]] = {}
        self._load_token_cache()

    def _load_token_cache(self):
        """Carrega cache de tokens comuns"""
        # Tokens pré-definidos
        self._token_cache = {
            "SOL-USDC": (SOLANA_TOKENS["SOL"], SOLANA_TOKENS["USDC"]),
            "SOL-USDT": (SOLANA_TOKENS["SOL"], SOLANA_TOKENS["USDT"]),
            "BONK-USDC": (SOLANA_TOKENS["BONK"], SOLANA_TOKENS["USDC"]),
            "JUP-USDC": (SOLANA_TOKENS["JUP"], SOLANA_TOKENS["USDC"]),
        }

    def _parse_symbol(self, symbol: str) -> tuple[str, str]:
        """
        Converte símbolo (ex: 'SOL-USDC') para mints (input_mint, output_mint).

        Args:
            symbol: Símbolo no formato 'TOKEN1-TOKEN2'

        Returns:
            Tuple com (input_mint, output_mint)
        """
        if symbol in self._token_cache:
            return self._token_cache[symbol]

        # Tenta parsear o símbolo
        parts = symbol.split("-")
        if len(parts) != 2:
            raise ValueError(f"Símbolo inválido: {symbol}. Use formato 'TOKEN1-TOKEN2'")

        token1, token2 = parts

        # Busca nos tokens conhecidos
        input_mint = SOLANA_TOKENS.get(token1)
        output_mint = SOLANA_TOKENS.get(token2)

        if not input_mint or not output_mint:
            raise ValueError(
                f"Token não encontrado: {token1 if not input_mint else token2}. "
                f"Tokens disponíveis: {list(SOLANA_TOKENS.keys())}"
            )

        self._token_cache[symbol] = (input_mint, output_mint)
        return input_mint, output_mint

    def get_ticker(self, symbol: str) -> TickerData:
        """
        Obtém ticker de um par específico usando Jupiter.

        Args:
            symbol: Símbolo do par (ex: 'SOL-USDC')

        Returns:
            TickerData: Dados do ticker
        """
        input_mint, output_mint = self._parse_symbol(symbol)

        # Obtém quote para 1 unidade do token de entrada
        # Para SOL: 1 SOL = 1_000_000_000 lamports
        amount = 1_000_000

        try:
            buy_quote = self.jupiter_api.get_quote(
                input_mint=input_mint,
                output_mint=output_mint,
                amount=amount,
                slippage_bps=50,
            )

            # Calcula o preço: output_amount / input_amount
            buy_price = (
                Decimal(buy_quote.in_amount) / Decimal(buy_quote.out_amount) / 10
            )

            quote_sell = self.jupiter_api.get_quote(
                input_mint=output_mint,
                output_mint=input_mint,
                amount=amount,
                slippage_bps=50,
            )
            sell_price = (
                Decimal(quote_sell.out_amount) / Decimal(quote_sell.in_amount) / 10
            )

            spread = (sell_price - buy_price) / buy_price * 100

            # Cria TickerData com os dados disponíveis
            # Nota: Jupiter não fornece OHLC, então usamos o preço atual para todos
            return TickerData(
                buy=buy_price,
                timestamp=datetime.now(),
                high=buy_price,  # Não disponível, usa preço atual
                last=buy_price,
                low=buy_price,  # Não disponível, usa preço atual
                open=buy_price,  # Não disponível, usa preço atual
                pair=symbol,
                sell=sell_price,
                vol=Decimal("0"),  # Não disponível via quote API
                spread=spread,
            )

        except Exception as e:
            self.logger.error(f"Erro ao obter ticker para {symbol}: {e}")
            raise

    def get_candles(
        self, symbol: str, start_date: datetime, end_date: datetime, resolution: str
    ) -> Candles:
        """
        Obtém candles de um par específico.

        NOTA: Jupiter não fornece dados históricos de candles diretamente.
        Esta implementação retorna candles vazios.
        Para dados históricos, use um provedor de dados como Birdeye ou DexScreener.

        Args:
            symbol: Símbolo do par
            start_date: Data de início
            end_date: Data de fim
            resolution: Resolução do candle

        Returns:
            Candles: Candles vazios (Jupiter não fornece histórico)
        """
        self.logger.warning(
            "Jupiter não fornece dados históricos de candles. "
            "Retornando candles vazios. "
            "Use Birdeye API ou DexScreener para dados históricos."
        )

        return Candles(
            close=[],
            high=[],
            low=[],
            open=[],
            timestamp=[],
            volume=[],
        )


class JupiterPrivateAPIAdapter(PrivateAPIBase):
    """
    Adaptador da API privada Jupiter para a interface base.

    NOTA: Jupiter funciona de forma diferente do Mercado Bitcoin:
    - Não há conceito de "contas" centralizadas
    - Usa wallets Solana descentralizadas
    - Não há histórico de ordens centralizado

    Este adaptador simula a interface para compatibilidade,
    mas muitas funcionalidades são limitadas ou não aplicáveis.
    """

    def __init__(
        self,
        wallet_public_key: str,
        rpc_url: str = "https://api.mainnet-beta.solana.com",
    ):
        """
        Inicializa o adaptador Jupiter privado.

        Args:
            wallet_public_key: Chave pública da wallet Solana
            rpc_url: URL do RPC endpoint da Solana
        """
        self.wallet_public_key = wallet_public_key
        self.rpc_url = rpc_url
        self.logger = logging.getLogger(__name__)

        # Simula uma conta única (wallets Solana não têm múltiplas contas)
        self._account_id = "solana_wallet"

    def get_accounts(self) -> List[AccountData]:
        """
        Retorna uma "conta" simulada representando a wallet Solana.

        Returns:
            List[AccountData]: Lista com uma conta simulada
        """
        return [
            AccountData(
                id=self._account_id,
                currency="USDC",
                currencySign="◎",
                name="Solana Wallet",
                type="wallet",
            )
        ]

    def get_account_balance(self, account_id: str) -> List[AccountBalanceData]:
        """
        Obtém saldo da wallet Solana.

        NOTA: Requer implementação de RPC calls para Solana.
        Por enquanto, retorna lista vazia.

        Args:
            account_id: ID da conta (ignorado, usa wallet_public_key)

        Returns:
            List[AccountBalanceData]: Lista de saldos
        """
        self.logger.warning(
            "get_account_balance não implementado para Jupiter. "
            "Requer integração com Solana RPC para obter saldos de tokens."
        )

        # TODO: Implementar chamada RPC para getTokenAccountsByOwner
        return []

    def place_order(
        self, account_id: str, symbol: str, side: str, type_order: str, quantity: str
    ) -> str:
        """
        Executa um swap na Jupiter.

        NOTA: Esta é uma implementação simplificada.
        Para execução real, requer:
        1. Obter quote
        2. Obter transação serializada
        3. Assinar com private key
        4. Enviar para blockchain

        Args:
            account_id: ID da conta (ignorado)
            symbol: Símbolo do par (ex: 'SOL-USDC')
            side: 'buy' ou 'sell'
            type_order: Tipo da ordem (apenas 'market' suportado)
            quantity: Quantidade a negociar

        Returns:
            str: Transaction signature (simulado)
        """
        raise NotImplementedError(
            "place_order requer implementação completa de wallet Solana. "
            "Use JupiterPrivateAPI.get_swap_transaction() diretamente "
            "e implemente a assinatura/envio com sua própria wallet."
        )

    def get_orders(
        self, symbol: str | None = None, status: str | None = None
    ) -> Dict[str, Any]:
        """
        Lista ordens.

        NOTA: Jupiter/Solana não mantém histórico centralizado de ordens.
        Para histórico, consulte a blockchain diretamente ou use um indexador.

        Args:
            symbol: Filtrar por símbolo (ignorado)
            status: Filtrar por status (ignorado)

        Returns:
            Dict vazio
        """
        self.logger.warning(
            "get_orders não aplicável para Jupiter. "
            "Consulte a blockchain Solana diretamente para histórico de transações."
        )

        return {"orders": []}


class FakeJupiterPrivateAPI(JupiterPrivateAPIAdapter):
    """
    Versão fake da API privada Jupiter para testes e backtesting.
    Simula operações sem executar transações reais.
    """

    def __init__(self):
        super().__init__(wallet_public_key="FAKE_WALLET_KEY")
        self._balances: Dict[str, Decimal] = {
            "SOL": Decimal("10.0"),
            "USDC": Decimal("100.0"),
            "BONK": Decimal("1000"),
        }

    def get_account_balance(self, account_id: str) -> List[AccountBalanceData]:
        """Retorna saldos simulados"""
        balances = []
        for symbol, amount in self._balances.items():
            balances.append(
                AccountBalanceData(
                    symbol=symbol,
                    available=amount,
                    on_hold=Decimal("0"),
                    total=amount,
                )
            )
        return balances

    def place_order(
        self, account_id: str, symbol: str, side: str, type_order: str, quantity: str
    ) -> str:
        """Simula execução de ordem"""
        import uuid

        order_id = str(uuid.uuid4())
        self.logger.info(
            f"[FAKE] Order placed: {side} {quantity} {symbol} - ID: {order_id}"
        )

        # Atualiza saldos simulados
        # TODO: Implementar lógica de atualização de saldo

        return order_id
