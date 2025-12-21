from datetime import datetime
from solders.pubkey import Pubkey

from trader.models import TickerData, SOLANA_MINTS

import logging
from decimal import Decimal
from typing import List

from solders.keypair import Keypair
from solders.solders import SendTransactionResp
from solders.transaction import VersionedTransaction

from trader.models.account_data import MintBalance
from trader.providers.jupiter.async_jupiter_client import AsyncJupiterClient, Interval
from trader.providers.jupiter.async_rpc_client import AsyncRPCClient
from trader.providers.jupiter.jupiter_data import JupiterQuoteResponse


class AsyncJupiterProvider:
    def __init__(
        self, keypair: Keypair, rpc_client=None, jupiter_client=None, is_dryrun=False
    ):
        self.keypair = keypair

        self.rpc_client = rpc_client or AsyncRPCClient(is_dryrun=is_dryrun)
        self.jupiter_client = jupiter_client or AsyncJupiterClient()
        self.logger = logging.getLogger(__name__)

    async def get_candles(
        self,
        mint: Pubkey,
        interval: Interval = Interval.SECOND_15,
        candle_qty: int = 100,
    ) -> list[TickerData]:
        return await self.jupiter_client.get_candles(str(mint))

    async def get_price_ticker_data(self, mint: Pubkey) -> TickerData:
        price = await self.jupiter_client.get_price(str(mint))
        return TickerData(
            buy=price,
            timestamp=datetime.now(),
            high=price,  # Não disponível, usa preço atual
            last=price,
            low=price,  # Não disponível, usa preço atual
            open=price,  # Não disponível, usa preço atual
            pair="ignored",
            sell=price,
            vol=Decimal("0"),  # Não disponível via quote API
        )

    async def get_account_balance(self) -> List[MintBalance]:
        balances = []

        # Saldo de SOL (lamports)
        amount = await self.rpc_client.get_lamports(self.keypair.pubkey())
        solana_mint = SOLANA_MINTS.get_by_symbol("SOL")
        _amount = amount / (10**solana_mint.decimals)
        balances.append(
            MintBalance(
                available=_amount,
                mint=solana_mint.pubkey,
            )
        )

        mint_balances = await self.rpc_client.get_account_balance(self.keypair.pubkey())
        for mint, amount in mint_balances.items():
            mint_info = SOLANA_MINTS.get(mint)
            if not mint_info:
                continue
            _amount = amount / (10**mint_info.decimals)
            balances.append(MintBalance(available=_amount, mint=mint))
        return balances

    async def swap(
        self,
        input_mint: Pubkey,
        output_mint: Pubkey,
        type_order: str,
        quantity: Decimal,
        price: Decimal | None = None,
    ) -> str:
        amount_in = quantity * price if price else quantity
        input_mint_info = SOLANA_MINTS[input_mint]
        amount_in = amount_in * (10**input_mint_info.decimals)
        amount_in = int(amount_in)
        return await self._do_swap_with_retry(
            str(input_mint), str(output_mint), amount_in
        )

    async def _do_swap_with_retry(
        self, input_mint: str, output_mint: str, amount_in: int
    ):
        for i in range(3):
            try:
                return await self._do_swap(
                    input_mint, output_mint, amount_in, [50, 50, 75][i]
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
        input_mint: str,
        output_mint: str,
        amount_in: int,
        slippage_bps: int = 50,
    ) -> JupiterQuoteResponse:
        quote = await self.jupiter_client.get_quote(
            input_mint, output_mint, amount_in, slippage_bps
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
        return await self.rpc_client.sign_transaction(tx, self.keypair)

    async def _send_signed_transaction(
        self, new_tx: VersionedTransaction
    ) -> SendTransactionResp:
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
        input_mint: str,
        output_mint: str,
        amount_in: int,
        slippage_bps: int = 50,
    ):
        quote = await self._get_quote_with_route(
            input_mint, output_mint, amount_in, slippage_bps
        )
        tx = await self._get_swap_transaction(quote)
        new_tx = await self._get_signed_transaction(tx)
        resp = await self._send_transaction_and_wait_for_confirmation(new_tx)
        return resp.to_json()
