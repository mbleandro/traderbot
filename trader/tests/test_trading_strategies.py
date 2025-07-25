"""
Testes function-based para estratégias de trading.
Validam comportamento de compra e venda com mínimo de mocking.
"""

from datetime import datetime
from decimal import Decimal

from trader.account import Position, Sides
from trader.trading_strategy import (
    HardPriceStrategy,
    PercentualPositionStrategy,
    SimpleMovingAverageStrategy,
)

order_counter = 1


def create_position(
    quantity: Decimal = Decimal("0.1"),
    entry_price: Decimal = Decimal("100.0"),
    current_price: Decimal | None = None,
) -> Position:
    """Helper para criar posições de teste"""
    global order_counter
    order_counter += 1
    return Position(
        order_id=f"test-order-{order_counter}",
        symbol="BTC-BRL",
        side=Sides.LONG,
        quantity=quantity,
        entry_price=entry_price,
        entry_time=datetime.now(),
        current_price=current_price or entry_price,
    )


def test_simple_moving_average_strategy_buy_signal():
    """Testa se SMA strategy compra quando SMA curta cruza acima da longa"""
    strategy = SimpleMovingAverageStrategy(short_period=3, long_period=5)

    # Preços que criam tendência de baixa seguida de alta
    prices = [
        Decimal("100"),
        Decimal("95"),
        Decimal("90"),
        Decimal("85"),
        Decimal("80"),  # SMA longa baixa
        Decimal("85"),
        Decimal("90"),
        Decimal("95"),  # SMA curta sobe
    ]

    position = create_position()

    # Alimenta histórico de preços
    for price in prices:
        strategy.update_price(price, position)

    # Deve comprar quando SMA curta > SMA longa
    assert strategy.should_buy(Decimal("95")) is True

    # SMA curta (3): (85+90+95)/3 = 90
    # SMA longa (5): (80+85+90+95)/4 = 87.5 (só tem 4 valores dos últimos 5)
    # Como 90 > 87.5, deve comprar


def test_simple_moving_average_strategy_sell_signal():
    """Testa se SMA strategy vende quando SMA curta cruza abaixo da longa"""
    strategy = SimpleMovingAverageStrategy(short_period=3, long_period=5)

    # Preços que criam tendência de alta seguida de baixa
    prices = [
        Decimal("80"),
        Decimal("85"),
        Decimal("90"),
        Decimal("95"),
        Decimal("100"),  # SMA longa alta
        Decimal("95"),
        Decimal("90"),
        Decimal("85"),  # SMA curta desce
    ]

    position = create_position()

    # Alimenta histórico de preços
    for price in prices:
        strategy.update_price(price, position)

    # Deve vender quando SMA curta < SMA longa
    assert strategy.should_sell(Decimal("85"), position) is True


def test_simple_moving_average_strategy_insufficient_data():
    """Testa se SMA strategy não opera sem dados suficientes"""
    strategy = SimpleMovingAverageStrategy(short_period=10, long_period=30)
    position = create_position()

    # Apenas alguns preços (insuficientes para long_period)
    for price in [Decimal("100"), Decimal("101"), Decimal("102")]:
        strategy.update_price(price, position)

    # Não deve comprar nem vender sem dados suficientes
    assert strategy.should_buy(Decimal("103")) is False
    assert strategy.should_sell(Decimal("103"), position) is False


def test_percentual_position_strategy_initial_buy():
    """Testa se strategy percentual compra na primeira vez (position_price_lock = 0)"""
    strategy = PercentualPositionStrategy(
        percentual_stop_loss=Decimal("0.1"), percentual_gain_treshold=Decimal("0.2")
    )

    # Sem posição inicial, deve comprar
    assert strategy.should_buy(Decimal("100")) is True


def test_percentual_position_strategy_stop_loss_nao_vende_se_preco_aumenta():
    """Testa se strategy percentual não vende se preço aumenta após stop loss"""
    strategy = PercentualPositionStrategy(
        percentual_stop_loss=Decimal("0.1"),  # 10% de stop loss
        percentual_gain_treshold=Decimal("0.1"),
    )

    market_price = Decimal("50")
    position = create_position(entry_price=market_price, quantity=Decimal("1.0"))
    strategy.update_price(market_price, position)
    assert strategy._price_stop_loss() == Decimal("45")
    assert strategy._price_gain_treshold() == Decimal("55")

    market_price = Decimal("100")
    assert strategy.should_sell(market_price, position) is False

    position = create_position(entry_price=market_price, quantity=Decimal("1.0"))
    strategy.update_price(market_price, position)

    assert strategy._price_stop_loss() == Decimal("90")
    assert strategy._price_gain_treshold() == Decimal("110")


def test_percentual_position_strategy_stop_loss():
    """Testa se strategy percentual vende no stop loss"""
    strategy = PercentualPositionStrategy(
        percentual_stop_loss=Decimal("0.1"),  # 10% de stop loss
        percentual_gain_treshold=Decimal("0.1"),
    )

    market_price = Decimal("100")
    position = create_position(entry_price=market_price, quantity=Decimal("1.0"))
    strategy.update_price(market_price, position)
    print(strategy.price_history)
    assert strategy._price_stop_loss() == Decimal("90")
    assert strategy._price_gain_treshold() == Decimal("110")

    market_price = Decimal("80")
    assert strategy.should_sell(market_price, position) is True

    market_price = Decimal("50")
    position = create_position(entry_price=market_price, quantity=Decimal("1.0"))
    strategy.update_price(market_price, position)

    assert strategy._price_stop_loss() == Decimal("45")
    assert strategy._price_gain_treshold() == Decimal("55")


def test_percentual_position_strategy_gain_lock():
    """Testa se strategy percentual atualiza price lock quando atinge gain threshold"""
    strategy = PercentualPositionStrategy(
        percentual_stop_loss=Decimal("0.1"),
        percentual_gain_treshold=Decimal("0.2"),  # 20% de gain threshold
    )

    # Simula entrada em R$ 100
    strategy.position_price_lock = Decimal("100")
    position = create_position(entry_price=Decimal("100"))

    # Preço sobe para R$ 125 (25% de alta, acima do threshold de 20%)
    new_price = Decimal("125")
    strategy.update_price(new_price, position)

    # Price lock deve ser atualizado para o novo preço
    assert strategy.position_price_lock == Decimal("125")


def test_hard_price_strategy_initial_buy():
    """Testa se strategy de preço absoluto compra na primeira vez (price_lock = 0)"""
    strategy = HardPriceStrategy(
        hard_stop_loss=Decimal("10"), hard_gain_treshold=Decimal("20")
    )

    # Adiciona pelo menos um preço ao histórico
    position = create_position()
    strategy.update_price(Decimal("100"), position)

    # Com price_lock inicial = 0, deve comprar (condição: price_history[-1] < market_price or price_lock == 0)
    assert strategy.should_buy(Decimal("101")) is True


def test_hard_price_strategy_stop_loss():
    """Testa se strategy de preço absoluto vende no stop loss"""
    strategy = HardPriceStrategy(
        hard_stop_loss=Decimal("10"),  # R$ 10 de stop loss
        hard_gain_treshold=Decimal("20"),
    )

    # Simula entrada em R$ 100
    strategy.price_lock = Decimal("100")
    position = create_position(entry_price=Decimal("100"))

    # Preço cai para R$ 85 (abaixo do stop loss de R$ 90)
    market_price = Decimal("85")

    # Deve vender (stop loss em R$ 90)
    assert strategy.should_sell(market_price, position) is True


def test_hard_price_strategy_gain_lock():
    """Testa se strategy de preço absoluto atualiza price lock quando atinge gain threshold"""
    strategy = HardPriceStrategy(
        hard_stop_loss=Decimal("10"),
        hard_gain_treshold=Decimal("20"),  # R$ 20 de gain threshold
    )

    # Simula entrada em R$ 100
    strategy.price_lock = Decimal("100")
    position = create_position(entry_price=Decimal("100"))

    # Preço sobe para R$ 125 (acima do threshold de R$ 120)
    new_price = Decimal("125")
    strategy.update_price(new_price, position)

    # Price lock deve ser atualizado para o novo preço
    assert strategy.price_lock == Decimal("125")


def test_calculate_quantity_methods():
    """Testa se os métodos de cálculo de quantidade funcionam corretamente"""
    balance = Decimal("1000")
    price = Decimal("100")

    # SMA strategy usa 10% do saldo
    sma_strategy = SimpleMovingAverageStrategy()
    sma_quantity = sma_strategy.calculate_quantity(balance, price)
    expected_sma = (balance * Decimal("0.1")) / price  # 1.0
    assert Decimal(sma_quantity) == expected_sma

    # Percentual e Hard strategies usam 80% do saldo
    percentual_strategy = PercentualPositionStrategy()
    percentual_quantity = percentual_strategy.calculate_quantity(balance, price)
    expected_percentual = (balance * Decimal("0.8")) / price  # 8.0
    assert Decimal(percentual_quantity) == expected_percentual

    hard_strategy = HardPriceStrategy()
    hard_quantity = hard_strategy.calculate_quantity(balance, price)
    assert Decimal(hard_quantity) == expected_percentual
