from datetime import datetime
from decimal import Decimal

from trader.models.order import Order, OrderSide
from trader.models.position import Position, PositionType
from trader.models.public_data import TickerData
from trader.trading_strategy import RandomStrategy


def _ticker_data(price: float) -> TickerData:
    _price = Decimal(f"{price}")
    symbol = "SOL-USDC"
    return TickerData(
        buy=_price,
        timestamp=datetime.now(),
        high=_price,
        last=_price,
        low=_price,
        open=_price,
        pair=symbol,
        sell=_price,
        vol=Decimal("0"),
        # spread=Decimal("-99.7500"),
    )


def test_random_strategy_buy():
    strategy = RandomStrategy(sell_chance=100, buy_chance=100)
    balance = Decimal("1000")
    order_signal = strategy.on_market_refresh(
        _ticker_data(price=10.0001), balance, current_position=None
    )
    assert order_signal
    assert order_signal.side == "buy"


def test_random_strategy_sell():
    strategy = RandomStrategy(sell_chance=100, buy_chance=100)
    balance = Decimal("1000")
    order_signal = strategy.on_market_refresh(
        _ticker_data(price=10.0001),
        balance,
        current_position=Position(
            type=PositionType.LONG,
            entry_order=Order(
                order_id="1",
                symbol="SOL-USDC",
                quantity=Decimal("10"),
                price=Decimal("10.0001"),
                side=OrderSide.BUY,
                timestamp=datetime.now(),
            ),
            exit_order=None,
        ),
    )
    assert order_signal
    assert order_signal.side == "sell"
