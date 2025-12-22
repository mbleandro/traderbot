from typing import Any
from datetime import datetime
from decimal import Decimal
from trader.models import SOLANA_MINTS, Order, OrderSide, Position, PositionType
from trader.providers import AsyncJupiterProvider
from unittest.mock import AsyncMock, patch
from trader.async_account import AsyncAccount


async def test_buy():
    mi, mo = SOLANA_MINTS.get_by_symbol("SOL"), SOLANA_MINTS.get_by_symbol("USDC")
    acc = AsyncAccount(AsyncMock(spec=AsyncJupiterProvider), mi.pubkey, mo.pubkey)

    with patch.object(AsyncAccount, "can_buy", return_value=True):
        order = await acc.buy(Decimal("100.00"), Decimal("0.1"))

    assert order.input_mint == mi.mint
    assert order.output_mint == mo.mint
    assert order.quantity == Decimal("0.1")
    assert order.price == Decimal("100.0")
    assert order.side == OrderSide.BUY

    assert acc.current_position
    assert acc.current_position.entry_order == order
    assert acc.current_position.exit_order is None


async def test_sell():
    mi, mo = SOLANA_MINTS.get_by_symbol("SOL"), SOLANA_MINTS.get_by_symbol("USDC")
    acc = AsyncAccount(AsyncMock(spec=AsyncJupiterProvider), mi.pubkey, mo.pubkey)
    position = Position(
        PositionType.LONG,
        Order(
            "",
            mi.mint,
            mo.mint,
            Decimal("0.1"),
            Decimal("110.0"),
            OrderSide.BUY,
            datetime.now(),
        ),
        exit_order=None,
    )
    acc.current_position = position
    with patch.object(AsyncAccount, "can_sell", return_value=True):
        order = await acc.sell(Decimal("100.00"), Decimal("0.1"))

    assert order.input_mint == mi.mint
    assert order.output_mint == mo.mint
    assert order.quantity == Decimal("0.1")
    assert order.price == Decimal("100.0")
    assert order.side == OrderSide.SELL

    assert position.exit_order == order
    assert acc.current_position is None
