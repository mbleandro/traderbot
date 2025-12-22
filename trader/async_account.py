from functools import cached_property
from solders.pubkey import Pubkey
import logging
from datetime import datetime
from decimal import Decimal

from trader.providers.jupiter.async_jupiter_svc import AsyncJupiterProvider

from .models import OrderSide, Position, PositionType, TickerData, Order, SOLANA_MINTS


class AsyncAccount:
    """Classe responsável por gerenciar balanço, posições e execução de ordens"""

    def __init__(
        self, provider: AsyncJupiterProvider, input_mint: Pubkey, output_mint: Pubkey
    ):
        self.provider = provider
        self.input_mint = input_mint
        self.output_mint = output_mint

        self.current_position: Position | None = None
        self.logger = logging.getLogger("Account")
        self.total_pnl = Decimal("0.0")

    async def get_price(self, mint: Pubkey) -> TickerData:
        return await self.provider.get_price_ticker_data(mint)

    async def get_candles(self, mint: Pubkey) -> list[TickerData]:
        return await self.provider.get_candles(mint)

    async def get_balance(self, mint: Pubkey) -> Decimal:
        """Obtém saldo de uma moeda específica"""
        balances = await self.provider.get_account_balance()
        for balance in balances:
            if balance.mint == mint:
                return Decimal(str(balance.available))
        return Decimal("0.0")

    def get_position(self) -> Position | None:
        """Retorna a posição atual"""
        return self.current_position

    async def can_buy(self) -> bool:
        """Verifica se é possível executar uma compra"""
        # Não pode comprar se já tem posição long
        if (
            self.current_position is not None
            and self.current_position.type == PositionType.LONG
        ):
            return False

        brl_balance = await self.get_balance(self.input_mint)
        print(self.input_mint, brl_balance)
        return brl_balance > Decimal("0.01")  # Mínimo para operar

    async def can_sell(self) -> bool:
        """Verifica se é possível executar uma venda"""
        # Só pode vender se tem posição long
        if (
            self.current_position is None
            or self.current_position.type != PositionType.LONG
        ):
            return False

        btc_balance = await self.get_balance(self.output_mint)
        return btc_balance > Decimal("0.00001")  # Mínimo para vender

    async def place_order(
        self, price: Decimal, side: OrderSide, quantity: Decimal
    ) -> Order:
        if side == OrderSide.BUY:
            return await self.buy(price, quantity)
        if side == OrderSide.SELL:
            return await self.sell(price, quantity)

        raise ValueError("Invalid Order Side.")

    async def buy(self, price: Decimal, quantity: Decimal) -> Order:
        if not await self.can_buy():
            raise ValueError("Não é possível executar compra no momento")
        try:
            order_id = await self.provider.swap(
                self.input_mint,
                self.output_mint,
                type_order="market",
                quantity=quantity,
                price=price,
            )
            order = Order(
                order_id=order_id,
                input_mint=str(self.input_mint),
                output_mint=str(self.output_mint),
                quantity=quantity,
                price=price,
                side=OrderSide.BUY,
                timestamp=datetime.now(),
            )
            # Criar nova posição
            self.current_position = Position(
                type=PositionType.LONG,
                entry_order=order,
                exit_order=None,
            )
            return order

        except Exception as ex:
            self.logger.error(f"Erro ao executar ordem: {str(ex)}")
            raise

    async def sell(self, price: Decimal, quantity: Decimal) -> Order:
        if not await self.can_sell():
            raise ValueError("Não é possível executar venda no momento")

        try:
            order_id = await self.provider.swap(
                self.output_mint,
                self.input_mint,
                type_order="market",
                quantity=quantity,
            )
            order = Order(
                order_id=order_id,
                input_mint=str(self.input_mint),
                output_mint=str(self.output_mint),
                quantity=quantity,
                price=price,
                side=OrderSide.SELL,
                timestamp=datetime.now(),
            )
            assert self.current_position
            self.current_position.exit_order = order
            self.total_pnl += self.current_position.realized_pnl
            self.current_position = None

            return order

        except Exception as ex:
            self.logger.error(f"Erro ao executar ordem: {str(ex)}")
            raise

    def get_total_realized_pnl(self) -> Decimal:
        return self.total_pnl

    def get_unrealized_pnl(self, current_price: Decimal) -> Decimal:
        """Retorna o PnL não realizado da posição atual"""
        if self.current_position:
            return self.current_position.unrealized_pnl(current_price)
        return Decimal("0.0")
