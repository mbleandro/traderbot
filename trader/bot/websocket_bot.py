from trader.models.bot_config import BotConfig
from aiohttp.web import head
import requests
from requests.api import request
import asyncio
import json
import traceback
from datetime import datetime
from decimal import Decimal

import websockets
import websockets.asyncio
import websockets.asyncio.client
from rich.console import Console
from rich.text import Text

from trader.bot.base_bot import BaseBot
from trader.models.order import Order
from trader.models.position import Position
from trader.models.public_data import TickerData

console = Console()


class WebsocketTradingBot(BaseBot):
    def __init__(self, config: BotConfig):
        super().__init__(config)
        self.total_pnl = Decimal("0.0")
        self.in_symbol, self.out_symbol = self.symbol.split("-")
        self.token = {
            "SOL": "So11111111111111111111111111111111111111112",
            "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
            "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
            "JUP": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
            "PUMP": "pumpCmXqMfrsAkQ5r49WcJnRayYRqmXz6ae8H7H9Dfn",
            "TURBO": "2Dyzu65QA9zdX1UeE7Gx71k7fiwyUK6sZdrvJ7auq5wm",
        }[self.in_symbol]

    async def get_current_ticker(
        self, ws: websockets.asyncio.client.ClientConnection
    ) -> TickerData:
        msg = await ws.recv()
        # '{"type":"prices","data":[{"assetId":"DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263","price":0.000010537070513205161,"blockId":380968492}]}'
        json_msg = json.loads(msg)
        price = Decimal(json_msg["data"][0]["price"])
        return TickerData(
            buy=price,
            timestamp=datetime.now(),
            high=price,  # Não disponível, usa preço atual
            last=price,
            low=price,  # Não disponível, usa preço atual
            open=price,  # Não disponível, usa preço atual
            pair=self.symbol,
            sell=price,
            vol=Decimal("0"),  # Não disponível via quote API
        )

    def run(self, **kwargs):
        self.is_running = True
        self.strategy.setup(self.get_candles())
        asyncio.run(self._run())

    async def connect_ws(self):
        return await websockets.connect(
            "wss://trench-stream.jup.ag/ws",
            additional_headers={"Origin": "https://jup.ag"},
            compression="deflate",
        )

    def get_candles(self) -> list[TickerData]:
        end_time = int(datetime.now().timestamp() * 1000)
        url = (
            f"https://datapi.jup.ag/v2/charts/{self.token}"
            f"?interval=15_SECOND&to={end_time}&candles=100&type=price&quote=usd"
        )
        response = None
        try:
            response = requests.get(
                url,
                headers={
                    "Origin": "https://jup.ag",
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0",
                },
            )
            response_json = response.json()
        except Exception as ex:
            ex.add_note(f"URL: {url}")
            if response is not None:
                ex.add_note(f"Status Code: {response.status_code}")
                ex.add_note(f"Response: {response.text}")
            raise ex
        tickers: list[TickerData] = []
        for candle in response_json["candles"]:
            tickers.append(
                TickerData(
                    pair=self.symbol,
                    timestamp=datetime.fromtimestamp(candle["time"]),
                    high=Decimal(candle["high"]),
                    low=Decimal(candle["low"]),
                    open=Decimal(candle["open"]),
                    last=Decimal(candle["close"]),
                    buy=Decimal(candle["open"]),
                    sell=Decimal(candle["open"]),
                    vol=Decimal(candle["volume"]),
                )
            )
        return tickers

    async def _run(self):
        should_stop = False
        while not should_stop:
            try:
                ws = await self.connect_ws()
                await ws.send(
                    json.dumps({"type": "subscribe:prices", "assets": [self.token]})
                )
                self.notification_service.send_message(
                    f"Bot iniciado para {self.symbol}"
                )

                while True:
                    try:
                        current_ticker = await self.get_current_ticker(ws)
                        log_ticker(
                            self.symbol,
                            current_ticker.last,
                            self.account.get_total_realized_pnl(),
                        )

                        order = self.process_market_data(current_ticker)
                        if order:
                            log_placed_order(order)
                            self.notification_service.send_message(
                                f"Ordem executada: {order.side.upper()} "
                                f"{order.quantity:.8f} {self.symbol} @ "
                                f"{self.in_symbol} {order.price:.2f}"
                            )

                        position = self.account.get_position()
                        if position:
                            log_position(position, current_ticker.last)

                    except websockets.exceptions.ConnectionClosedError:
                        self.logger.warning(
                            "Conexão WebSocket perdida. Reconnectando..."
                        )
                        self.notification_service.send_message(
                            "Conexão WebSocket perdida. Reconnectando..."
                        )
                        break  # Sai do loop interno e volta para tentar reconectar

                    except KeyboardInterrupt:
                        self.logger.warning("Bot interrompido pelo usuário")
                        self.notification_service.send_message(
                            "Bot interrompido pelo usuário"
                        )
                        should_stop = True
                        return

                    except Exception as ex:
                        self.logger.error(f"Erro no loop principal: {str(ex)}")
                        traceback.print_exc()

            except Exception as ex:
                self.logger.error(f"Erro ao conectar WebSocket: {str(ex)}")
                await asyncio.sleep(2)  # Espera antes de tentar reconectar


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
