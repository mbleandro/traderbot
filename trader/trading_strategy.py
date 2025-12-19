from tkinter import W
from datetime import datetime, timedelta
import random
from abc import ABC, abstractmethod
from decimal import Decimal

import pandas as pd

from trader.models.public_data import TickerData

from .models import OrderSide, OrderSignal, Position


class TradingStrategy(ABC):
    """Classe base para estratégias de trading"""

    @abstractmethod
    def on_market_refresh(
        self,
        ticker: TickerData,
        balance: Decimal | None,
        current_position: Position | None,
    ) -> OrderSignal | None:
        pass

    @abstractmethod
    def calculate_quantity(self, balance: Decimal, price: Decimal) -> Decimal:
        pass

    def setup(self, ticker_history: list[TickerData]):
        """Configura a estratégia, se necessário"""
        pass


class RandomStrategy(TradingStrategy):
    def __init__(self, sell_chance: int, buy_chance: int):
        self.buy_chance = buy_chance
        self.sell_chance = sell_chance
        self.price_history: list[Decimal] = []

    def calculate_quantity(self, balance: Decimal, price: Decimal) -> Decimal:
        quantity = (balance * Decimal("0.5")) / price
        return quantity

    def on_market_refresh(
        self,
        ticker: TickerData,
        balance: Decimal | None,
        current_position: Position | None,
    ) -> OrderSignal | None:
        self.price_history.append(ticker.last)
        if not current_position:
            if random.randint(1, 100) <= int(self.buy_chance):
                self.price_history = []
                return OrderSignal(OrderSide.BUY)
        else:
            if random.randint(1, 100) <= int(self.sell_chance):
                self.price_history = []
                return OrderSignal(
                    OrderSide.SELL, current_position.entry_order.quantity
                )
        return None


class TargetValueStrategy(TradingStrategy):
    """
    Estratégia de valor alvo com stop loss dinâmico.

    O bot compra quando o preço atinge um valor alvo configurado.
    Acompanha o valor até atingir um percentual de ganho configurado.
    Quando atingir esse percentual, ativa um stop loss de 1% (vende se cair 1%).

    Args:
        target_buy_price (Decimal|str): Preço alvo para compra
        target_profit_percent (Decimal|str): Percentual de ganho alvo (ex: 5 para 5%)
        stop_loss_percent (Decimal|str): Percentual de stop loss após atingir ganho alvo (padrão: 1 para 1%)
        balance_percent (Decimal|str): Percentual do saldo a usar na compra (padrão: 80 para 80%)
    """

    def __init__(
        self,
        target_buy_price: Decimal | str,
        target_profit_percent: Decimal | str,
        stop_loss_percent: Decimal | str = "1",
        balance_percent: Decimal | str = "80",
        max_spread: Decimal | str = "1.5",
    ):
        self.target_buy_price = Decimal(str(target_buy_price))
        self.target_profit_percent = Decimal(str(target_profit_percent))
        self.stop_loss_percent = Decimal(str(stop_loss_percent))
        self.balance_percent = Decimal(str(balance_percent))
        self.max_position_periods = 10
        self.max_spread = Decimal(str(max_spread))

        # Estado interno
        self.target_profit_reached = False
        self.highest_price_after_target = Decimal("0")
        self.position_periods = 0
        self.last_price = None
        self.price_history: list[Decimal] = []
        self.max_history_size = 60 * 60 * 4 / 10  # 4h
        self.same_target_count = 0
        self.report_interval = 60 * 60 / 10  # 1h

    def _recalculate_target_buy_price(self):
        """
        Calcula o target buy (preço-alvo de compra) com base em uma lista de preços históricos (Decimal).
        Segue a mesma lógica da função original, mas sem puxar dados de candles da API.
        """
        if len(self.price_history) < 200:
            return

        # -----------------------
        # 1. Converter lista em DataFrame
        # -----------------------
        df = pd.DataFrame({"c": [float(p) for p in self.price_history]})
        df.index = pd.RangeIndex(start=0, stop=len(df))

        # Como não temos high/low, podemos derivar deles:
        # assumindo que o preço oscilou ±0.2% em cada candle
        df["h"] = df["c"] * 1.005
        df["l"] = df["c"] * 0.995

        # -----------------------
        # 2. Calcular EMA50 e EMA200
        # -----------------------
        df["EMA50"] = df["c"].ewm(span=50, adjust=False).mean()
        df["EMA200"] = df["c"].ewm(span=200, adjust=False).mean()

        # -----------------------
        # 3. Calcular ATR (Average True Range)
        # -----------------------
        df["H-L"] = df["h"] - df["l"]
        df["H-PC"] = abs(df["h"] - df["c"].shift(1))
        df["L-PC"] = abs(df["l"] - df["c"].shift(1))
        df["TR"] = df[["H-L", "H-PC", "L-PC"]].max(axis=1)
        df["ATR"] = df["TR"].rolling(window=60).mean()

        # -----------------------
        # 4. Calcular RSI14
        # -----------------------
        delta = df["c"].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()
        rs = avg_gain / avg_loss
        df["RSI14"] = 100 - (100 / (1 + rs))

        # -----------------------
        # 5. Calcular Target Buy
        # -----------------------
        latest = df.iloc[-1]
        k = 1.5 if latest["EMA50"] > latest["EMA200"] else 2.2
        target_buy = latest["EMA50"] - k * latest["ATR"]

        # -----------------------
        # 6. Exibir resultados
        # -----------------------
        print(f"Último preço: {latest['c']:.8f}")
        print(f"EMA50: {latest['EMA50']:.8f}")
        print(f"EMA200: {latest['EMA200']:.8f}")
        print(f"ATR: {latest['ATR']:.8f}")
        print(f"RSI14: {latest['RSI14']:.2f}")
        print(f"Target buy calculado: {target_buy:.8f}")

        self.target_buy_price = target_buy

    def calculate_quantity(self, balance: Decimal, price: Decimal) -> Decimal:
        """Calcula a quantidade a comprar baseado no saldo disponível"""
        if balance >= Decimal("5"):
            return Decimal("5") / price
        quantity = (balance * (self.balance_percent / Decimal("100"))) / price
        return quantity

    def on_market_refresh(
        self,
        ticker: TickerData,
        balance: Decimal | None,
        current_position: Position | None,
    ) -> OrderSignal | None:
        current_price = ticker.buy

        self.price_history.append(current_price)
        self.same_target_count += 1
        if len(self.price_history) > self.max_history_size:
            self.price_history.pop(0)

        # Se não tem posição, verifica se deve comprar
        if not current_position:
            # if self.same_target_count > self.max_history_size:
            #     self._recalculate_target_buy_price()
            #     self.same_target_count = 0
            # Reset do estado quando não há posição
            self.target_profit_reached = False
            self.highest_price_after_target = Decimal("0")

            # Compra quando o preço atingir ou estiver abaixo do valor alvo
            if current_price <= self.target_buy_price:
                if ticker.spread is not None and ticker.spread > self.max_spread:
                    print(f"Skip buying for high spread = {ticker.spread}")
                    print(
                        f"Current price: {current_price}; target buy: {self.target_buy_price}; spread: {ticker.spread}"
                    )
                    return None
                if self.last_price is None or current_price < self.last_price:
                    print("Skip buying - waiting for price to stop dropping")
                    print(
                        f"Current price: {current_price}; target buy: {self.target_buy_price}; spread: {ticker.spread}"
                    )
                    self.last_price = current_price
                    return None
                self.position_periods = 0
                print(
                    f"Current price: {current_price} <= Target buy: {self.target_buy_price} - BUYING!"
                )
                return OrderSignal(OrderSide.BUY)
        else:
            # Tem posição aberta, verifica condições de venda
            entry_price = current_position.entry_order.price

            # Calcula o percentual de ganho atual
            profit_percent = ((current_price - entry_price) / entry_price) * Decimal(
                "100"
            )

            # Verifica se atingiu o ganho alvo
            if profit_percent >= self.target_profit_percent or (
                self.target_profit_reached
                and profit_percent >= self.target_profit_percent - Decimal("1.1")
            ):
                self.position_periods += 1
                if not self.target_profit_reached:
                    # Primeira vez que atinge o ganho alvo
                    self.target_profit_reached = True
                    self.highest_price_after_target = current_price

                # Atualiza o preço mais alto após atingir o ganho alvo
                if current_price > self.highest_price_after_target:
                    self.highest_price_after_target = current_price

                # Calcula a queda percentual desde o pico
                drop_percent = (
                    (self.highest_price_after_target - current_price)
                    / self.highest_price_after_target
                ) * Decimal("100")

                # if self.position_periods >= self.max_position_periods:
                #     print(f"Current price: {current_price} - SELLING!")
                #     return OrderSignal(
                #         OrderSide.SELL, current_position.entry_order.quantity
                #     )

                # Ativa stop loss se cair o percentual configurado
                if drop_percent >= self.stop_loss_percent:
                    print(f"Current price: {current_price} - SELLING!")
                    return OrderSignal(
                        OrderSide.SELL, current_position.entry_order.quantity
                    )

        msg = f"Current price: {current_price:.9f}; target buy: {self.target_buy_price:.9f}"
        print(msg)
        self.last_price = current_price
        return None


class DynamicTargetStrategy(TradingStrategy):
    """
    Estratégia de target dinâmico usando EMA (Exponential Moving Average) e ATR (Average True Range).

    O bot calcula um preço-alvo de compra dinâmico baseado na tendência (EMA) e volatilidade (ATR):
    - Target Buy = EMA - (ATR × buy_factor)
    - Target Sell = EMA + (ATR × sell_factor)

    Isso permite que o bot se adapte automaticamente às condições do mercado:
    - Em mercados voláteis (ATR alto), os targets ficam mais distantes
    - Em mercados calmos (ATR baixo), os targets ficam mais próximos

    Args:
        ema_period (int): Período da média móvel exponencial (padrão: 20)
        atr_period (int): Período do ATR (padrão: 14)
        buy_factor (Decimal|str): Multiplicador do ATR para calcular target de compra (padrão: 1.5)
        sell_factor (Decimal|str): Multiplicador do ATR para calcular target de venda (padrão: 1.5)
        balance_percent (Decimal|str): Percentual do saldo a usar na compra (padrão: 80)
        stop_loss_atr_factor (Decimal|str): Multiplicador do ATR para stop loss (padrão: 3.0)
    """

    def __init__(
        self,
        ema_period: int | str = "20",
        atr_period: int | str = "14",
        buy_factor: Decimal | str = "1.5",
        sell_factor: Decimal | str = "1.5",
        balance_percent: Decimal | str = "80",
        stop_loss_atr_factor: Decimal | str = "3.0",
    ):
        self.ema_period = int(ema_period)
        self.atr_period = int(atr_period)
        self.buy_factor = Decimal(str(buy_factor))
        self.sell_factor = Decimal(str(sell_factor))
        self.balance_percent = Decimal(str(balance_percent))
        self.stop_loss_atr_factor = Decimal(str(stop_loss_atr_factor))

        # Histórico de preços para cálculos
        self.ticker_history: list[TickerData] = []

        # Cache de EMA (para cálculo incremental)
        self.current_ema: Decimal | None = None

    def calculate_quantity(self, balance: Decimal, price: Decimal) -> Decimal:
        """Calcula a quantidade a comprar baseado no saldo disponível"""
        quantity = (balance * (self.balance_percent / Decimal("100"))) / price
        return quantity

    def calculate_ema(self, prices: list[Decimal], period: int) -> Decimal:
        """
        Calcula a EMA (Exponential Moving Average).

        EMA_t = EMA_{t-1} + α × (P_t - EMA_{t-1})
        onde α = 2 / (period + 1)
        """
        if len(prices) < period:
            # Se não temos dados suficientes, retorna a média simples
            return sum(prices) / Decimal(len(prices))

        # Fator de suavização
        alpha = Decimal("2") / Decimal(period + 1)

        # Se já temos EMA calculada, usa cálculo incremental
        if self.current_ema is not None:
            self.current_ema = self.current_ema + alpha * (
                prices[-1] - self.current_ema
            )
            return self.current_ema

        # Primeira vez: calcula SMA dos primeiros 'period' valores como seed
        sma = sum(prices[:period]) / Decimal(period)
        ema = sma

        # Aplica EMA para os valores restantes
        for price in prices[period:]:
            ema = ema + alpha * (price - ema)

        self.current_ema = ema
        return ema

    def calculate_true_range(
        self, current: TickerData, previous: TickerData
    ) -> Decimal:
        """
        Calcula o True Range de um período.

        TR = max(High - Low, |High - Close_prev|, |Low - Close_prev|)
        """
        high_low = current.high - current.low
        high_close = abs(current.high - previous.last)
        low_close = abs(current.low - previous.last)

        return max(high_low, high_close, low_close)

    def calculate_atr(self, tickers: list[TickerData], period: int) -> Decimal:
        """
        Calcula o ATR (Average True Range).

        ATR é a média móvel simples dos True Ranges.
        """
        if len(tickers) < 2:
            # Não temos dados suficientes, usa o range do candle atual
            return tickers[-1].high - tickers[-1].low

        # Calcula True Range para cada período (precisa de pelo menos 2 candles)
        true_ranges: list[Decimal] = []
        for i in range(1, len(tickers)):
            tr = self.calculate_true_range(tickers[i], tickers[i - 1])
            true_ranges.append(tr)

        # Se não temos dados suficientes para o período completo, usa o que temos
        if len(true_ranges) < period:
            return sum(true_ranges) / Decimal(len(true_ranges))

        # Calcula a média dos últimos 'period' True Ranges
        recent_trs = true_ranges[-period:]
        atr = sum(recent_trs) / Decimal(period)

        return atr

    def on_market_refresh(
        self,
        ticker: TickerData,
        balance: Decimal | None,
        current_position: Position | None,
    ) -> OrderSignal | None:
        # Adiciona o ticker ao histórico
        self.ticker_history.append(ticker)

        # Precisamos de dados suficientes para calcular EMA e ATR
        min_required = max(self.ema_period, self.atr_period)
        if len(self.ticker_history) < min_required:
            return None

        current_price = ticker.last

        # Calcula EMA e ATR
        prices = [t.last for t in self.ticker_history]
        ema = self.calculate_ema(prices, self.ema_period)
        atr = self.calculate_atr(self.ticker_history, self.atr_period)

        # Calcula os targets dinâmicos
        target_buy = ema - (atr * self.buy_factor)
        target_sell = ema + (atr * self.sell_factor)
        stop_loss = ema - (atr * self.stop_loss_atr_factor)

        # Se não tem posição, verifica se deve comprar
        if not current_position:
            # Compra quando o preço cai abaixo do target dinâmico
            if current_price <= target_buy:
                assert balance
                return OrderSignal(
                    OrderSide.BUY,
                    self.calculate_quantity(balance, current_price),
                )
        else:
            # Tem posição aberta, verifica condições de venda

            # Vende quando atinge o target de venda (take profit)
            if current_price >= target_sell:
                return OrderSignal(
                    OrderSide.SELL, current_position.entry_order.quantity
                )

            # Stop loss: vende se cair muito abaixo da EMA
            if current_price <= stop_loss:
                return OrderSignal(
                    OrderSide.SELL, current_position.entry_order.quantity
                )

        return None


class WeightedMovingAverageStrategy(TradingStrategy):
    """
    Estratégia baseada em médias móveis ponderadas.
    Apenas compra quando a média curta está abaixo da média longa.
    A venda acontece seguindo a estratégia de target value.
    """

    def __init__(
        self,
        short_window: int = 15,
        long_window: int = 200,
        buy_when_short_below: bool = True,
        period: int = 60,
        shift_past: int = 0,
    ):
        self.short_window = short_window
        self.long_window = long_window
        self.buy_when_short_below = buy_when_short_below
        self.period = period
        self.shift_past = shift_past

        self.price_history: list[Decimal] = []
        self.last_price_time = datetime.min

    def calculate_quantity(self, balance: Decimal, price: Decimal) -> Decimal:
        quantity = (balance * Decimal("0.8")) / price
        return quantity

    def weighted_moving_average(self, prices: list[Decimal], window: int) -> Decimal:
        if self.shift_past > 0:
            prices = prices[: -self.shift_past]

        weights = list(range(1, window + 1))
        weighted_prices = [
            price * Decimal(weight) for price, weight in zip(prices[-window:], weights)
        ]
        return sum(weighted_prices) / Decimal(sum(weights))

    def set_parameters(self, price: Decimal, timestamp: datetime | None = None):
        history_limit = self.long_window + self.shift_past
        _now: datetime = datetime.now() if timestamp is None else timestamp
        if self.last_price_time + timedelta(seconds=self.period) <= _now:
            self.price_history.append(price)
            self.last_price_time = _now
            if len(self.price_history) > history_limit:
                self.price_history.pop(0)

        if self.last_price_time + timedelta(seconds=self.period) > _now:
            # substitui o ultimo preco da lista enquanto o periodo de atualizacao nao chega
            # pra evitar que a media fique defasada
            self.price_history[-1] = price

    def setup(self, ticker_history):
        for ticker in ticker_history:
            self.set_parameters(ticker.last, ticker.timestamp)
        return super().setup(ticker_history)

    def on_market_refresh(
        self,
        ticker: TickerData,
        balance: Decimal | None,
        current_position: Position | None,
    ) -> OrderSignal | None:
        self.set_parameters(ticker.last)

        if len(self.price_history) < self.long_window:
            return None

        short_wma = self.weighted_moving_average(self.price_history, self.short_window)
        long_wma = self.weighted_moving_average(self.price_history, self.long_window)
        print(
            f"{self.__class__.__name__}: Short: {short_wma:.9f}; Long: {long_wma:.9f} {self.buy_when_short_below=} {self.shift_past=}"
            f" can_buy={not current_position is not None and ((self.buy_when_short_below and short_wma < long_wma) or (not self.buy_when_short_below and short_wma > long_wma))}"
        )
        if not current_position:
            if self.buy_when_short_below and short_wma < long_wma:
                return OrderSignal(OrderSide.BUY)

            if not self.buy_when_short_below and short_wma > long_wma:
                return OrderSignal(OrderSide.BUY)

        return None


class TrailingStopLossStrategy(TradingStrategy):
    """
    Estratégia de stop loss dinâmico.
    Acompanha o preço após a compra e ativa um stop loss quando o preço cai um percentual configurado.
    """

    def __init__(
        self,
        stop_loss_percent: Decimal | str = "1",
        balance_percent: Decimal | str = "80",
    ):
        self.stop_loss_percent = Decimal(str(stop_loss_percent))
        self.balance_percent = Decimal(str(balance_percent))

        # Estado interno
        self.highest_price_after_target = Decimal("0")

    def calculate_quantity(self, balance: Decimal, price: Decimal) -> Decimal:
        """Calcula a quantidade a comprar baseado no saldo disponível"""
        if balance >= Decimal("5"):
            return Decimal("5") / price
        quantity = (balance * (self.balance_percent / Decimal("100"))) / price
        return quantity

    def on_market_refresh(
        self,
        ticker: TickerData,
        balance: Decimal | None,
        current_position: Position | None,
    ) -> OrderSignal | None:
        current_price = ticker.buy

        # Se não tem posição, verifica se deve comprar
        if not current_position:
            # Essa estratégia não contempla compra. Deixa o composer decidir.
            # Reset do estado quando não há posição
            self.highest_price_after_target = Decimal("0")
            return OrderSignal(OrderSide.BUY)
        else:
            # Atualiza o preço mais alto após atingir o ganho alvo
            if current_price > self.highest_price_after_target:
                self.highest_price_after_target = current_price

            # Calcula a queda percentual desde o pico
            drop_percent = (
                (self.highest_price_after_target - current_price)
                / self.highest_price_after_target
            ) * Decimal("100")
            print(
                f"StopLossStrategy: drop_percent={drop_percent:.2f}% from highest_price={self.highest_price_after_target:.9f} to current_price={current_price:.9f}"
            )
            # Ativa stop loss se cair o percentual configurado
            if drop_percent >= self.stop_loss_percent:
                return OrderSignal(
                    OrderSide.SELL, current_position.entry_order.quantity
                )

        return None


class TargetPercentStrategy(TradingStrategy):
    """
    Estratégia de Porcentagem de lucro alvo.
    Ao conseguir porcentagem, vende.

    """

    def __init__(
        self,
        target_percent: Decimal | str = "1",
        balance_percent: Decimal | str = "80",
    ):
        self.target_percent = Decimal(str(target_percent))
        self.balance_percent = Decimal(str(balance_percent))

        # Estado interno

    def calculate_quantity(self, balance: Decimal, price: Decimal) -> Decimal:
        """Calcula a quantidade a comprar baseado no saldo disponível"""
        if balance >= Decimal("5"):
            return Decimal("5") / price
        quantity = (balance * (self.balance_percent / Decimal("100"))) / price
        return quantity

    def on_market_refresh(
        self,
        ticker: TickerData,
        balance: Decimal | None,
        current_position: Position | None,
    ) -> OrderSignal | None:
        current_price = ticker.buy

        # Se não tem posição, verifica se deve comprar
        if not current_position:
            # Essa estratégia não contempla compra. Deixa o composer decidir.
            # Reset do estado quando não há posição
            return OrderSignal(OrderSide.BUY)
        else:
            # Calcula o percentual do preco atual em relacão a posicao atual
            current_percent = (
                (current_price - current_position.entry_order.price) / current_price
            ) * Decimal("100")
            print(
                f"StopLossStrategy: drop_percent={current_percent:.2f}% from entry_order.price={current_position.entry_order.price:.9f} to current_price={current_price:.9f}"
            )
            # Ativa stop loss se cair o percentual configurado
            if current_percent >= self.target_percent:
                return OrderSignal(
                    OrderSide.SELL, current_position.entry_order.quantity
                )

        return None


class StrategyComposer(TradingStrategy):
    """
    Compositor de estratégias de trading.
    Combina múltiplas estratégias e executa caso todas sejam válidas.
    """

    # def __init__(self, strategies: list[TradingStrategy]):
    def __init__(self, sell_mode=str("all"), buy_mode=str("all")):
        assert sell_mode in ("all", "any")
        assert buy_mode in ("all", "any")
        self.sell_mode = sell_mode
        self.buy_mode = buy_mode

        self.buy_strategies = [
            WeightedMovingAverageStrategy(
                short_window=25, long_window=100, buy_when_short_below=True, period=15
            ),
            WeightedMovingAverageStrategy(
                short_window=6,
                long_window=12,
                buy_when_short_below=True,
                period=15,
                shift_past=10,
            ),
            WeightedMovingAverageStrategy(
                short_window=6, long_window=12, buy_when_short_below=False, period=15
            ),
        ]
        self.sell_strategies = [
            TrailingStopLossStrategy(stop_loss_percent="0.2"),
            TargetPercentStrategy(target_percent="0.5"),
        ]

    def calculate_quantity(self, balance: Decimal, price: Decimal) -> Decimal:
        # Usa a estratégia principal (primeira da lista) para calcular a quantidade
        return self.buy_strategies[0].calculate_quantity(balance, price)

    def setup(self, ticker_history):
        for strategy in self.buy_strategies + self.sell_strategies:
            strategy.setup(ticker_history)
        return super().setup(ticker_history)

    def _check_signals(self, signals, mode: str, side: OrderSide) -> bool:
        if mode == "all":
            return all(s and s.side == side for s in signals)
        elif mode == "any":
            return any(s and s.side == side for s in signals)
        return False

    def on_market_refresh(
        self,
        ticker: TickerData,
        balance: Decimal | None,
        current_position: Position | None,
    ) -> OrderSignal | None:
        signals = []
        if current_position:
            for strategy in self.sell_strategies:
                signal = strategy.on_market_refresh(ticker, balance, current_position)
                signals.append(signal)
            if self._check_signals(signals, self.sell_mode, OrderSide.SELL):
                print(f"Strategy SELL")
                return OrderSignal(
                    OrderSide.SELL, current_position.entry_order.quantity
                )
        else:
            for strategy in self.buy_strategies:
                signal = strategy.on_market_refresh(ticker, balance, current_position)
                signals.append(signal)
            if self._check_signals(signals, self.buy_mode, OrderSide.BUY):
                print(f"Strategy BUY")
                return OrderSignal(OrderSide.BUY)

        return None
