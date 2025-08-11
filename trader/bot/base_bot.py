from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal

from trader.account import Account
from trader.api import MercadoBitcoinPublicAPI
from trader.colored_logger import get_trading_logger
from trader.models.position import Position
from trader.models.public_data import TickerData
from trader.report import ReportBase
from trader.trading_strategy import TradingStrategy


class BaseBot(ABC):
    """Classe base para bots de trading e backtesting"""

    def __init__(
        self,
        api: MercadoBitcoinPublicAPI,
        strategy: TradingStrategy,
        report: ReportBase,
        account: Account,
        enable_logging: bool = True,
    ):
        self.api = api
        self.strategy = strategy
        self.symbol = account.symbol
        self.is_running = False
        self.account = account
        self.report = report

        self.ticker_history: list[TickerData] = []
        self.last_position: Position | None = None

        # Configurar logging colorido
        self.trading_logger = get_trading_logger(
            self.__class__.__name__, enable_logging
        )
        self.logger = self.trading_logger.get_logger()

    @abstractmethod
    def run(self, **kwargs):
        """Método abstrato para executar o bot"""
        pass

    def process_market_data(
        self, current_ticker: TickerData, timestamp: datetime | None = None
    ):
        """Processa dados de mercado e executa lógica de trading comum"""
        self.ticker_history.append(current_ticker)

        position_signal = self.strategy.on_market_refresh(
            current_ticker,
            self.account.get_balance("BRL"),
            self.account.get_position(),
            self.account.position_history,
        )

        if position_signal:
            order = self.account.place_order(
                current_ticker.last,
                position_signal.side,
                position_signal.quantity,
            )
            self.trading_logger.log_order_placed(
                order.order_id,
                order.side,
                order.price,
                order.quantity,
            )
        self.log_account_info()

    def log_account_info(self):
        # Log de informações da conta
        position = self.account.get_position()
        if position:
            self.trading_logger.log_position(
                position.type,
                float(position.entry_order.quantity),
                float(position.entry_order.price),
            )
        elif self.account.position_history:
            last_position = self.account.position_history[-1]
            if last_position != self.last_position:
                self.last_position = last_position
                realized_pnl = last_position.realized_pnl
                if realized_pnl > 0:
                    self.logger.info(
                        f"Posição fechada com LUCRO - PnL: R$ {realized_pnl:.2f}"
                    )
                else:
                    self.logger.info(
                        f"Posição fechada com PREJUÍZO - PnL: R$ {realized_pnl:.2f}"
                    )

        # Log de PnL
        unrealized_pnl = (
            position.unrealized_pnl(self.ticker_history[-1].last)
            if position
            else Decimal("0.0")
        )
        if position:
            self.trading_logger.log_unrealized_pnl(float(unrealized_pnl))

        total_pnl = self.account.get_total_realized_pnl()
        self.trading_logger.log_realized_pnl(float(total_pnl))

    def stop(self):
        """Para o bot"""
        self.is_running = False
        self.trading_logger.log_bot_stop()
        self.report.add_ticker_history(self.ticker_history)
        self.report.add_position_history(self.account.position_history)
        self.report.generate_report()
