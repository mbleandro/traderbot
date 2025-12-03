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
        position_history: list[Position],
    ) -> OrderSignal | None:
        pass

    @abstractmethod
    def calculate_quantity(self, balance: Decimal, price: Decimal) -> Decimal:
        pass


class IterationStrategy(TradingStrategy):
    """
    Estratégia baseada em número de iterações.

    Compra na primeira oportunidade e vende após um número específico de iterações.
    Utiliza 80% do saldo disponível para cada operação de compra.

    Args:
        sell_on_iteration (int): Número de iterações para vender
    """

    def __init__(self, sell_on_iteration: int, buy_on_iteration: int):
        self.sell_on_iteration = sell_on_iteration
        self.buy_on_iteration = buy_on_iteration
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
        position_history: list[Position],
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
        balance: Decimal,
        current_position: Position | None,
        position_history: list[Position],
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
