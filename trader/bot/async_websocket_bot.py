from trader.providers import SOLANA_TOKENS
from solders.pubkey import Pubkey
from trader.async_account import AsyncAccount
import logging
from trader.models.bot_config import BotConfig
import asyncio
import traceback
from decimal import Decimal

import websockets
from rich.console import Console
from rich.text import Text

from trader.models.order import Order
from trader.models.position import Position
from trader.models.public_data import TickerData
from trader.providers.jupiter.async_jupiter_client import AsyncJupiterClient
from trader.providers.jupiter.jupiter_public_api import (
    SOLANA_TOKENS_BY_MINT,
    SOLANA_TOKENS_DECIMALS,
)

console = Console()


class AsyncWebsocketTradingBot:
    def __init__(
        self,
        config: BotConfig,
    ):
        self.last_position: Position | None = None
        self.is_running = False
        self.logger = logging.getLogger(self.__class__.__name__)

        self.mint_in = Pubkey.from_string(config.mint_in)
        self.mint_out = Pubkey.from_string(config.mint_out)

        self.symbol = f"{SOLANA_TOKENS_BY_MINT[str(self.mint_out)]}-{SOLANA_TOKENS_BY_MINT[str(self.mint_in)]}"

        self.strategy = config.strategy
        self.account = AsyncAccount(
            config.provider,  # type: ignore
            self.mint_in,
            self.mint_out,
        )
        self.notification_service = config.notifier

        self.total_pnl = Decimal("0.0")

    async def process_market_data(self, current_ticker: TickerData):
        position_signal = self.strategy.on_market_refresh(
            current_ticker,
            await self.account.get_balance(self.mint_in),
            self.account.get_position(),
        )
        order = None
        if position_signal:
            order = await self.account.place_order(
                current_ticker.last,
                position_signal.side,
                position_signal.quantity,
            )
        return order

    def stop(self):
        """Para o bot"""
        self.is_running = False

    def run(self, **kwargs):
        self.is_running = True
        asyncio.run(self._run())

    async def _run(self):
        self.strategy.setup(await self.account.get_candles(self.mint_out))
        should_stop = False
        self.notification_service.send_message(f"Bot iniciado para {self.symbol}")

        while not should_stop:
            try:
                current_ticker = await self.account.get_price(self.mint_out)
                log_ticker(
                    self.symbol,
                    current_ticker.last,
                    self.account.get_total_realized_pnl(),
                )

                order = await self.process_market_data(current_ticker)
                if order:
                    log_placed_order(order)
                    self.notification_service.send_message(
                        f"Ordem executada: {order.side.upper()} "
                        f"{order.quantity:.8f} {self.symbol} @ "
                        f"{self.symbol.split('-')[1]} {order.price:.2f}"
                    )

                position = self.account.get_position()
                if position:
                    log_position(position, current_ticker.last)

            except websockets.exceptions.ConnectionClosedError:
                self.logger.warning("Conexão WebSocket perdida. Reconnectando...")
                self.notification_service.send_message(
                    "Conexão WebSocket perdida. Reconnectando..."
                )
                break  # Sai do loop interno e volta para tentar reconectar

            except KeyboardInterrupt:
                self.logger.warning("Bot interrompido pelo usuário")
                self.notification_service.send_message("Bot interrompido pelo usuário")
                should_stop = True
                return

            except Exception as ex:
                self.logger.error(f"Erro no loop principal: {str(ex)}")
                traceback.print_exc()


def log_ticker(symbol: str, price: Decimal, realized_pnl: Decimal | None = None):
    fiat_symbol = symbol.split("-")[1]
    if realized_pnl is not None:
        console.print(
            f"[blue]{symbol}[/blue] @ {fiat_symbol} {price:.9f}. PNL Realizado: R$ {realized_pnl:.9f}"
        )
    else:
        console.print(f"[blue]{symbol}[/blue] @ {fiat_symbol} {price:.9f}.")


def log_placed_order(order: Order):
    console.print(
        *[
            Text(
                order.side.upper(),
                style="bold red" if order.side == "sell" else "bold green",
            ),
            Text(f"{order.quantity:.8f} @ R$ {order.price:.2f}", style="bold white"),
            Text(f"({order.order_id})", style="dim blue"),
        ]
    )


def log_position(position: Position, current_price: Decimal):
    pnl = (
        position.unrealized_pnl_percent(current_price)
        if position.exit_order is None
        else position.realized_pnl_percent
    )
    pnl_style = "bold green" if pnl > 0 else "bold red"
    pnl_str = f"[{pnl_style}]{pnl:.2f}%[/{pnl_style}]"

    console.print(
        f"{position.type.name} {position.entry_order.quantity:.8f} @ R$ {position.entry_order.price:.2f}. PNL: {pnl_str}"
    )
