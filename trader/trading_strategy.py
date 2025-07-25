from abc import ABC, abstractmethod
from decimal import Decimal

from .account import Position


class TradingStrategy(ABC):
    """Classe base para estratégias de trading"""

    price_history: list[Decimal]

    @abstractmethod
    def should_buy(self, market_price: Decimal) -> bool:
        pass

    @abstractmethod
    def should_sell(self, market_price: Decimal, position: Position) -> bool:
        pass

    @abstractmethod
    def calculate_quantity(self, balance: Decimal, price: Decimal) -> str:
        pass

    @abstractmethod
    def update_price(self, price: Decimal, position: Position | None):
        pass


class SimpleMovingAverageStrategy(TradingStrategy):
    """Estratégia baseada em média móvel simples"""

    def __init__(self, short_period: int = 10, long_period: int = 30):
        self.short_period = short_period
        self.long_period = long_period
        self.price_history = []

    def update_price(self, price: Decimal, position: Position | None):
        """Atualiza histórico de preços"""
        self.price_history.append(price)
        if len(self.price_history) > self.long_period:
            self.price_history.pop(0)

    def _calculate_sma(self, period: int) -> Decimal:
        """Calcula média móvel simples"""
        if len(self.price_history) < period:
            return Decimal("0")
        return sum(self.price_history[-period:]) / Decimal(str(period))

    def should_buy(self, market_price: Decimal) -> bool:
        """Compra quando SMA curta cruza acima da SMA longa"""
        if len(self.price_history) < self.long_period:
            return False

        short_sma = self._calculate_sma(self.short_period)
        long_sma = self._calculate_sma(self.long_period)

        return short_sma > long_sma

    def should_sell(self, market_price: Decimal, position: Position) -> bool:
        """Vende quando SMA curta cruza abaixo da SMA longa"""
        if len(self.price_history) < self.long_period:
            return False

        short_sma = self._calculate_sma(self.short_period)
        long_sma = self._calculate_sma(self.long_period)

        return short_sma < long_sma

    def calculate_quantity(self, balance: Decimal, price: Decimal) -> str:
        """Calcula quantidade baseada em 10% do saldo"""
        quantity = (balance * Decimal("0.1")) / price
        return f"{quantity:.8f}"


class PercentualPositionStrategy(TradingStrategy):
    """Estratégia baseada em valores percentuais da posição"""

    def __init__(
        self,
        percentual_stop_loss: Decimal = Decimal("0.10"),
        percentual_gain_treshold: Decimal = Decimal("0.30"),
    ):
        self.percentual_stop_loss = percentual_stop_loss
        self.percentual_gain_treshold = percentual_gain_treshold
        self.price_history = []
        self.last_position_id = None
        self.position_price_lock: Decimal = Decimal("0")
        self.price_lock: Decimal = Decimal("0")

    def _price_stop_loss(self) -> Decimal:
        """Calcula preço de stop loss baseado no percentual"""
        return self.position_price_lock * (Decimal("1") - self.percentual_stop_loss)

    def _price_gain_treshold(self) -> Decimal:
        """Calcula preço de gain threshold baseado no percentual"""
        return self.position_price_lock * (Decimal("1") + self.percentual_gain_treshold)

    def update_price(self, price: Decimal, position: Position | None):
        """Atualiza histórico de preços"""
        self.price_history.append(price)
        if price >= self._price_gain_treshold() or (
            position and position.order_id != self.last_position_id
        ):
            self.price_lock = price
            self.last_position_id = position.order_id if position else None
            self.position_price_lock = price

    def should_buy(self, market_price: Decimal) -> bool:
        _should_buy = (
            market_price < self._price_stop_loss() or not self.last_position_id
        )
        return _should_buy

    def should_sell(self, market_price: Decimal, position: Position) -> bool:
        position_price = market_price * position.quantity
        _should_sell = position_price < self._price_stop_loss()
        return _should_sell

    def calculate_quantity(self, balance: Decimal, price: Decimal) -> str:
        quantity = (balance * Decimal("0.8")) / price
        return f"{quantity:.8f}"

    def __str__(self):
        return f"PercentualPositionStrategy(price_stop_loss={self._price_stop_loss()}, price_gain_treshold={self._price_gain_treshold()})"


class HardPriceStrategy(TradingStrategy):
    """Estratégia baseada em valores absolutos de preço"""

    def __init__(
        self,
        hard_stop_loss: Decimal = Decimal("0.10"),
        hard_gain_treshold: Decimal = Decimal("0.30"),
    ):
        self.hard_stop_loss = hard_stop_loss
        self.hard_gain_treshold = hard_gain_treshold
        self.price_history = []
        self.price_lock: Decimal = Decimal("0")
        self.last_position_id = None

    def _price_stop_loss(self) -> Decimal:
        """Calcula preço de stop loss baseado no valor absoluto"""
        return self.price_lock - self.hard_stop_loss

    def _price_gain_treshold(self) -> Decimal:
        """Calcula preço de gain threshold baseado no valor absoluto"""
        return self.price_lock + self.hard_gain_treshold

    def update_price(self, price: Decimal, position: Position | None):
        """Atualiza histórico de preços"""
        self.price_history.append(price)
        if price >= self._price_gain_treshold() or (
            position and position.order_id != self.last_position_id
        ):
            self.price_lock = price
            self.last_position_id = position.order_id if position else None

    def should_buy(self, market_price: Decimal) -> bool:
        _should_buy = self.price_history[-1] < market_price or not self.last_position_id
        return _should_buy

    def should_sell(self, market_price: Decimal, position: Position) -> bool:
        _should_sell = market_price < self._price_stop_loss()
        return _should_sell

    def calculate_quantity(self, balance: Decimal, price: Decimal) -> str:
        quantity = (balance * Decimal("0.8")) / price
        return f"{quantity:.8f}"

    def __str__(self):
        return f"HardPriceStrategy(price_stop_loss={self._price_stop_loss()}, price_gain_treshold={self._price_gain_treshold()})"
