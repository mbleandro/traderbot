from datetime import datetime
from decimal import Decimal

from trader.models.order import Order, OrderSide
from trader.models.position import Position, PositionType
from trader.models.public_data import TickerData
from trader.trading_strategy import RandomStrategy


def test_random_strategy_buy():
    strategy = RandomStrategy(sell_chance=100, buy_chance=100)
    balance = Decimal("1000")
    order_signal = strategy.on_market_refresh(
        Decimal("10.0001"),
        Decimal("0.0001"),
        balance,
        current_position=None,
    )
    assert order_signal
    assert order_signal.side == "buy"


def test_random_strategy_sell():
    strategy = RandomStrategy(sell_chance=100, buy_chance=100)
    balance = Decimal("1000")
    order_signal = strategy.on_market_refresh(
        Decimal("10.0001"),
        Decimal("0.0001"),
        balance,
        current_position=Position(
            type=PositionType.LONG,
            entry_order=Order(
                order_id="1",
                input_mint="Sol1111",
                output_mint="Efwr4t",
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
