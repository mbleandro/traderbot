"""
Testes function-based para estratégias de trading.
Validam comportamento de compra e venda com mínimo de mocking.
"""

from datetime import datetime
from decimal import Decimal

from trader.models import Position, PositionType, TickerData
from trader.models.order import Order, OrderSide
from trader.trading_strategy import (
    RandomForestStrategy,
    SimpleMovingAverageStrategy,
)

order_counter = 1


def create_position(
    quantity: Decimal = Decimal("0.1"),
    entry_price: Decimal = Decimal("100.0"),
) -> Position:
    """Helper para criar posições de teste"""
    global order_counter
    order_counter += 1
    return Position(
        type=PositionType.LONG,
        entry_order=Order(
            order_id=f"test-order-{order_counter}",
            symbol="BTC-BRL",
            quantity=quantity,
            price=entry_price,
            side=OrderSide.BUY,
            time=datetime.now(),
        ),
        exit_order=None,
    )


def create_ticker(price: Decimal) -> TickerData:
    """Helper para criar objetos TickerData de teste"""
    return TickerData(
        buy=price - Decimal("1"),
        date=int(datetime.now().timestamp()),
        high=price + Decimal("5"),
        last=price,
        low=price - Decimal("5"),
        open=price,
        pair="BTC-BRL",
        sell=price + Decimal("1"),
        vol=Decimal("100"),
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
    balance = Decimal("1000")

    # Alimenta histórico de preços
    for price in prices:
        ticker = create_ticker(price)
        strategy.on_market_refresh(ticker, balance, position, [])

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
    balance = Decimal("1000")

    # Alimenta histórico de preços
    for price in prices:
        ticker = create_ticker(price)
        strategy.on_market_refresh(ticker, balance, position, [])

    # Deve vender quando SMA curta < SMA longa
    assert strategy.should_sell(Decimal("85"), position) is True


def test_simple_moving_average_strategy_insufficient_data():
    """Testa se SMA strategy não opera sem dados suficientes"""
    strategy = SimpleMovingAverageStrategy(short_period=10, long_period=30)
    position = create_position()
    balance = Decimal("1000")

    # Apenas alguns preços (insuficientes para long_period)
    for price in [Decimal("100"), Decimal("101"), Decimal("102")]:
        ticker = create_ticker(price)
        strategy.on_market_refresh(ticker, balance, position, [])

    # Não deve comprar nem vender sem dados suficientes
    assert strategy.should_buy(Decimal("103")) is False
    assert strategy.should_sell(Decimal("103"), position) is False


def test_calculate_quantity_methods():
    """Testa se os métodos de cálculo de quantidade funcionam corretamente"""
    balance = Decimal("1000")
    price = Decimal("100")

    # SMA strategy usa 10% do saldo
    sma_strategy = SimpleMovingAverageStrategy()
    sma_quantity = sma_strategy.calculate_quantity(balance, price)
    expected_sma = (balance * Decimal("0.1")) / price  # 1.0
    assert Decimal(sma_quantity) == expected_sma


def test_random_forest_strategy_initialization():
    """Testa se RandomForest strategy inicializa corretamente"""
    strategy = RandomForestStrategy(
        retrain_interval=30, min_data_points=50, prediction_threshold=0.7
    )

    assert strategy.retrain_interval == 30
    assert strategy.min_data_points == 50
    assert strategy.prediction_threshold == 0.7
    assert strategy.model is None
    assert len(strategy.price_history) == 0
    assert len(strategy.volume_history) == 0


def test_random_forest_strategy_insufficient_data():
    """Testa se RandomForest strategy não opera sem dados suficientes"""
    strategy = RandomForestStrategy(min_data_points=100)
    balance = Decimal("1000")

    # Apenas alguns preços (insuficientes para treinar modelo)
    for price in [Decimal("100"), Decimal("101"), Decimal("102")]:
        ticker = create_ticker(price)
        signal = strategy.on_market_refresh(ticker, balance, None, [])

        # Não deve gerar sinais sem dados suficientes
        assert signal is None


def test_random_forest_strategy_data_accumulation():
    """Testa se RandomForest strategy acumula dados corretamente"""
    strategy = RandomForestStrategy(min_data_points=10)
    balance = Decimal("1000")

    # Alimenta com dados suficientes
    prices = [Decimal(str(100 + i)) for i in range(25)]
    volumes = [Decimal(str(1000 + i * 10)) for i in range(25)]

    for price, volume in zip(prices, volumes):
        ticker = TickerData(
            buy=price - Decimal("1"),
            date=int(datetime.now().timestamp()),
            high=price + Decimal("5"),
            last=price,
            low=price - Decimal("5"),
            open=price,
            pair="BTC-BRL",
            sell=price + Decimal("1"),
            vol=volume,
        )
        strategy.on_market_refresh(ticker, balance, None, [])

    # Verifica se dados foram acumulados
    assert len(strategy.price_history) == 25
    assert len(strategy.volume_history) == 25
    assert strategy.price_history[-1] == prices[-1]
    assert strategy.volume_history[-1] == volumes[-1]


def test_random_forest_strategy_technical_indicators():
    """Testa se RandomForest strategy calcula indicadores técnicos"""
    strategy = RandomForestStrategy()

    # Adiciona dados suficientes para calcular indicadores
    prices = [Decimal(str(100 + i)) for i in range(25)]
    volumes = [Decimal(str(1000 + i * 10)) for i in range(25)]

    strategy.price_history = prices
    strategy.volume_history = volumes

    indicators = strategy._calculate_technical_indicators()

    assert indicators is not None
    assert "sma_5" in indicators
    assert "sma_10" in indicators
    assert "sma_20" in indicators
    assert "rsi" in indicators
    assert "volume_sma_5" in indicators
    assert "volatility" in indicators
    assert "current_return" in indicators

    # Verifica se valores são razoáveis
    assert indicators["sma_5"] > 0
    assert indicators["sma_10"] > 0
    assert indicators["sma_20"] > 0
    assert 0 <= indicators["rsi"] <= 100


def test_random_forest_strategy_calculate_quantity():
    """Testa se RandomForest strategy calcula quantidade corretamente"""
    strategy = RandomForestStrategy()
    balance = Decimal("1000")
    price = Decimal("100")

    # RandomForest strategy usa 15% do saldo
    quantity = strategy.calculate_quantity(balance, price)
    expected = (balance * Decimal("0.15")) / price  # 1.5
    assert quantity == expected


def test_random_forest_strategy_history_limit():
    """Testa se RandomForest strategy limita o histórico corretamente"""
    strategy = RandomForestStrategy()
    balance = Decimal("1000")

    # Adiciona mais dados que o limite (200)
    for i in range(250):
        ticker = create_ticker(Decimal(str(100 + i)))
        strategy.on_market_refresh(ticker, balance, None, [])

    # Verifica se histórico foi limitado
    assert len(strategy.price_history) == 200
    assert len(strategy.volume_history) == 200
    assert len(strategy._features_cache) <= 200


def test_random_forest_strategy_initialize_historical_data():
    """Testa se RandomForest strategy inicializa com dados históricos"""
    from unittest.mock import Mock

    from trader.api.public_api import MercadoBitcoinPublicAPI
    from trader.models.public_data import Candles

    # Criar mock da API
    mock_api = Mock(spec=MercadoBitcoinPublicAPI)

    # Criar dados de candles simulados
    n_candles = 100
    mock_candles = Candles(
        close=[Decimal(str(100 + i)) for i in range(n_candles)],
        high=[Decimal(str(105 + i)) for i in range(n_candles)],
        low=[Decimal(str(95 + i)) for i in range(n_candles)],
        open=[Decimal(str(100 + i)) for i in range(n_candles)],
        volume=[Decimal(str(1000 + i * 10)) for i in range(n_candles)],
        timestamp=[
            1640995200 + i * 3600 for i in range(n_candles)
        ],  # Timestamps de hora em hora
    )

    mock_api.get_candles.return_value = mock_candles

    # Criar estratégia com parâmetros baixos para teste
    strategy = RandomForestStrategy(min_data_points=30)

    # Inicializar com dados históricos
    start_datetime = datetime(2022, 1, 1, 12, 0, 0)
    strategy.initialize_historical_data(
        interval=3600,  # 1 hora
        start_datetime=start_datetime,
        symbol="BTC-BRL",
        public_api=mock_api,
    )

    # Verificar se dados foram carregados
    assert len(strategy.price_history) == n_candles
    assert len(strategy.volume_history) == n_candles
    assert len(strategy.timestamp_history) == n_candles

    # Verificar se features foram calculadas
    assert len(strategy._features_cache) > 0

    # Verificar se API foi chamada corretamente
    mock_api.get_candles.assert_called_once()

    # Verificar se o modelo foi treinado (se houver dados suficientes)
    if len(strategy._features_cache) >= strategy.min_data_points:
        # Modelo deve ter sido treinado ou pelo menos tentado
        assert strategy.iteration_count == 0  # Ainda não processou dados em tempo real
