"""
Adaptadores para a API Jupiter que implementam as interfaces base.
Permite usar Jupiter com a mesma interface do Mercado Bitcoin.
"""

from trader.models import JupiterQuoteResponse

import logging
import os
from decimal import Decimal
from typing import List

from solders.keypair import Keypair
from solders.solders import SendTransactionResp
from solders.transaction import VersionedTransaction

from trader.providers.jupiter.async_jupiter_client import AsyncJupiterClient
from trader.providers.jupiter.async_rpc_client import AsyncRPCClient

from ...models.account_data import AccountBalanceData
from .jupiter_public_api import (
    SOLANA_TOKENS,
    SOLANA_TOKENS_BY_MINT,
    SOLANA_TOKENS_DECIMALS,
)


class AsyncJupiterService:
    """
    Adaptador da API privada Jupiter para a interface base.

    NOTA: Jupiter funciona de forma diferente do Mercado Bitcoin:
    - Não há conceito de "contas" centralizadas
    - Usa wallets Solana descentralizadas
    - Não há histórico de ordens centralizado

    Este adaptador simula a interface para compatibilidade,
    mas muitas funcionalidades são limitadas ou não aplicáveis.
    """

    @classmethod
    def from_env(cls):
        private_key = os.getenv("SOLANA_PRIVATE_KEY")
        assert private_key, "Chave privada não definida"
        keypair = Keypair.from_base58_string(private_key)
        return cls(keypair)

    def __init__(self, keypair: Keypair):
        self.keypair = keypair
        self.wallet = keypair.pubkey()
        self.wallet_public_key = str(keypair.pubkey())

        self.rpc_client = AsyncRPCClient()
        self.jupiter_client = AsyncJupiterClient()
        self.logger = logging.getLogger(__name__)

    async def get_account_balance(self) -> List[AccountBalanceData]:
        """
        Obtém saldo da wallet Solana.

        NOTA: Requer implementação de RPC calls para Solana.
        Por enquanto, retorna lista vazia.

        Returns:
            List[AccountBalanceData]: Lista de saldos
        """
        balances = []

        # ============================
        # 1 - Saldo de SOL (lamports)
        # ============================
        amount = await self.rpc_client.get_lamports(self.keypair.pubkey())
        decimals = SOLANA_TOKENS_DECIMALS["SOL"]
        balances.append(
            AccountBalanceData(
                available=amount / (10**decimals),
                on_hold=Decimal("0"),
                symbol="SOL",
                total=amount / (10**decimals),
            )
        )

        mint_balances = await self.rpc_client.get_account_balance(self.keypair.pubkey())
        for mint, amount in mint_balances.items():
            ticker_name = SOLANA_TOKENS_BY_MINT.get(str(mint))
            if not ticker_name:
                continue
            decimals = SOLANA_TOKENS_DECIMALS[ticker_name]
            balances.append(
                AccountBalanceData(
                    available=amount / (10**decimals),
                    on_hold=Decimal("0"),
                    symbol=ticker_name,
                    total=amount / (10**decimals),
                )
            )
        return balances

    async def buy(
        self,
        symbol: str,
        type_order: str,
        quantity: str,
        price: Decimal,
    ) -> str:
        mint_in = SOLANA_TOKENS[symbol.split("-")[0]]
        mint_out = SOLANA_TOKENS[symbol.split("-")[1]]

        mint_in, mint_out = mint_out, mint_in
        decimals = SOLANA_TOKENS_DECIMALS[symbol.split("-")[1]]
        amount_in = int(Decimal(quantity) * price * (10**decimals))
        return await self._do_swap_with_retry(mint_in, mint_out, amount_in)

    async def sell(
        self,
        symbol: str,
        type_order: str,
        quantity: str,
    ) -> str:
        mint_in = SOLANA_TOKENS[symbol.split("-")[0]]
        mint_out = SOLANA_TOKENS[symbol.split("-")[1]]

        decimals = SOLANA_TOKENS_DECIMALS[symbol.split("-")[0]]
        amount_in = int(Decimal(quantity) * (10**decimals))
        return await self._do_swap_with_retry(mint_in, mint_out, amount_in)

    async def _do_swap_with_retry(self, mint_in: str, mint_out: str, amount_in: int):
        for i in range(3):
            try:
                return await self._do_swap(
                    mint_in, mint_out, amount_in, [50, 50, 75][i]
                )
            except Exception as e:
                if i == 2:
                    raise e
                self.logger.warning(
                    f"Erro ao executar swap: {e}. Tentando novamente..."
                )
        raise Exception("Erro ao executar swap após múltiplas tentativas")

    async def _wait_for_confirmation(self, signature, timeout=30):
        print("→ Aguardando confirmação...")
        await self.rpc_client.wait_for_confirmation(signature, timeout)

    async def _get_quote_with_route(
        self,
        mint_in: str,
        mint_out: str,
        amount_in: int,
        slippage_bps: int = 50,
    ) -> JupiterQuoteResponse:
        quote = await self.jupiter_client.get_quote(
            mint_in, mint_out, amount_in, slippage_bps
        )

        if not quote.routePlan:
            raise Exception("Nenhuma rota encontrada!")

        print("✓ Rota encontrada.")
        return quote

    async def _get_swap_transaction(
        self, quote: JupiterQuoteResponse
    ) -> VersionedTransaction:
        return await self.jupiter_client.get_swap_transaction(
            quote, self.keypair.pubkey()
        )

    async def _get_signed_transaction(
        self, tx: VersionedTransaction
    ) -> VersionedTransaction:
        # ---------- assinar ----------
        return await self.rpc_client.sign_transaction(tx, self.keypair)

    async def _send_signed_transaction(
        self, new_tx: VersionedTransaction
    ) -> SendTransactionResp:
        # ---------- enviar ----------
        await self.rpc_client.simulate_transaction(new_tx)
        resp = await self.rpc_client.send_transaction(new_tx)
        signature = resp.value

        print(f"✓ Transação enviada: {signature}")
        return resp

    async def _send_transaction_and_wait_for_confirmation(
        self, new_tx: VersionedTransaction
    ) -> SendTransactionResp:
        resp = await self._send_signed_transaction(new_tx)
        signature = resp.value
        await self._wait_for_confirmation(signature)
        return resp

    async def _do_swap(
        self,
        mint_in: str,
        mint_out: str,
        amount_in: int,
        slippage_bps: int = 50,
    ):
        quote = await self._get_quote_with_route(
            mint_in, mint_out, amount_in, slippage_bps
        )
        tx = await self._get_swap_transaction(quote)
        new_tx = await self._get_signed_transaction(tx)
        resp = await self._send_transaction_and_wait_for_confirmation(new_tx)
        return resp.to_json()
