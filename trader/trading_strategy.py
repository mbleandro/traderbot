from abc import ABC, abstractmethod
from decimal import Decimal

from trader.models.public_data import TickerData

from .models import OrderSide, OrderSignal, Position


class TradingStrategy(ABC):
    """Classe base para estratégias de trading"""

    @abstractmethod
    def on_market_refresh(
        self,
        ticker: TickerData,
        balance: Decimal,
        current_position: Position | None,
        position_history: list[Position],
    ) -> OrderSignal | None:
        pass


class IterationStrategy(TradingStrategy):
    """
    Estratégia baseada em número de iterações.

    Compra na primeira oportunidade e vende após um número específico de iterações.
    Utiliza 80% do saldo disponível para cada operação de compra.

    Args:
        sell_on_iteration (int): Número de iterações para vender
    """

    def __init__(
        self,
        buy_on_iteration=2,
        sell_on_iteration=5,
    ):
        self.buy_on_iteration = int(buy_on_iteration)
        self.sell_on_iteration = int(sell_on_iteration)
        self.price_history: list[Decimal] = []

    def calculate_quantity(self, balance: Decimal, price: Decimal) -> Decimal:
        quantity = (balance * Decimal("0.8")) / price
        return quantity

    def on_market_refresh(
        self,
        ticker: TickerData,
        balance: Decimal,
        current_position: Position | None,
        position_history: list[Position],
    ) -> OrderSignal | None:
        self.price_history.append(ticker.last)
        if not current_position:
            if len(self.price_history) > self.buy_on_iteration:
                self.price_history = []
                return OrderSignal(
                    OrderSide.BUY,
                    self.calculate_quantity(balance, ticker.last),
                )
        else:
            if len(self.price_history) > self.sell_on_iteration:
                self.price_history = []
                return OrderSignal(
                    OrderSide.SELL, current_position.entry_order.quantity
                )
        return None
