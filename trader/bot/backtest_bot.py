import traceback
from datetime import datetime
from enum import Enum

from rich.progress import Progress

from trader.bot.base_bot import BaseBot
from trader.models.public_data import Candles
from trader.notification.notification_service import NullNotificationService


class IntervalResolution(Enum):
    ONE_MINUTE = (60, "1m")
    FIFTEEN_MINUTES = (900, "15m")
    ONE_HOUR = (3600, "1h")
    THREE_HOURS = (10800, "3h")
    ONE_DAY = (86400, "1d")
    ONE_WEEK = (604800, "1w")
    ONE_MONTH = (2592000, "1M")

    def __init__(self, seconds, label):
        self.seconds = seconds
        self.label = label

    @classmethod
    def from_seconds(cls, seconds: int):
        for item in cls:
            if item.seconds == seconds:
                return item
        raise ValueError(f"No resolution for interval {seconds}")

    @classmethod
    def to_resolution(cls, seconds: int) -> str:
        return cls.from_seconds(seconds).label


class BacktestingBot(BaseBot):
    """Bot para backtesting com dados históricos"""

    def __init__(self, api, strategy, report, account, start_datetime, end_datetime):
        # Desabilitar logging para backtesting
        super().__init__(
            api,
            strategy,
            report,
            account,
            enable_logging=False,
            notification_service=NullNotificationService(),
        )
        self.start_date_datetime = datetime.fromisoformat(start_datetime)
        self.end_date_datetime = datetime.fromisoformat(end_datetime)

    def get_historical_prices(self, resolution: str) -> Candles:
        return self.api.get_candles(
            self.symbol, self.start_date_datetime, self.end_date_datetime, resolution
        )

    def run(self, interval: int = 60):
        """Executa o backtesting com dados históricos"""

        candles = self.get_historical_prices(IntervalResolution.to_resolution(interval))

        total_candles = len(candles.close)
        last_order_id = None
        with Progress() as progress:
            task = progress.add_task("[green]Processando...", total=total_candles)
            for index in range(len(candles.close)):
                current_ticker = candles.get_ticker_from_index(index)
                try:
                    progress.update(task, advance=1)
                    self.process_market_data(current_ticker)

                    # sempre que houver uma ordem, deve atualizar o valor de timestamp, pra ficar coerente com o backtest.
                    if self.account.position_history:
                        last_pos = self.account.position_history[-1]
                        last_order = last_pos.exit_order or last_pos.entry_order
                        if last_order.order_id != last_order_id:
                            last_order_id = last_order.order_id
                            last_order.timestamp = datetime.fromtimestamp(
                                candles.timestamp[index]
                            )

                except KeyboardInterrupt:
                    progress.stop()
                    self.stop()
                    return
                except Exception:
                    traceback.print_exc()

        self.stop()
