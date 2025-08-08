from abc import abstractmethod
from datetime import datetime, timedelta
from decimal import Decimal

import numpy as np
from sklearn.ensemble import RandomForestClassifier

from trader.api.public_api import IntervalResolution, MercadoBitcoinPublicAPI
from trader.models.public_data import TickerData

from .models import OrderSide, OrderSignal, Position


class TradingStrategy:
    """Classe base para estratégias de trading"""

    def initialize_historical_data(
        self,
        interval: int,
        start_datetime: datetime,
        symbol: str,
        public_api: MercadoBitcoinPublicAPI,
    ):
        """Inicializa a estratégia com dados históricos"""
        pass

    @abstractmethod
    def on_market_refresh(
        self,
        ticker: TickerData,
        balance: Decimal,
        current_position: Position | None,
        position_history: list[Position],
    ) -> OrderSignal | None:
        pass


class SimpleMovingAverageStrategy(TradingStrategy):
    """Estratégia baseada em média móvel simples"""

    def __init__(self, short_period: int = 10, long_period: int = 30):
        self.short_period = short_period
        self.long_period = long_period
        self.price_history: list[Decimal] = []

    def initialize_historical_data(
        self,
        interval: int,
        start_datetime: datetime,
        symbol: str,
        public_api: MercadoBitcoinPublicAPI,
    ):
        candles = public_api.get_candles(
            symbol,
            start_datetime - timedelta(seconds=interval * self.long_period),
            start_datetime,
            IntervalResolution.to_resolution(interval),
        )
        self.price_history = candles.close

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

    def calculate_quantity(self, balance: Decimal, price: Decimal) -> Decimal:
        """Calcula quantidade baseada em 10% do saldo"""
        quantity = (balance * Decimal("0.1")) / price
        return quantity

    def on_market_refresh(
        self,
        ticker: TickerData,
        balance: Decimal,
        current_position: Position | None,
        position_history: list[Position],
    ) -> OrderSignal | None:
        self.price_history.append(ticker.last)
        if len(self.price_history) > self.long_period:
            self.price_history.pop(0)

        if not current_position:
            if self.should_buy(ticker.last):
                return OrderSignal(
                    OrderSide.BUY, self.calculate_quantity(balance, ticker.last)
                )
        else:
            if self.should_sell(ticker.last, current_position):
                return OrderSignal(
                    OrderSide.SELL, current_position.entry_order.quantity
                )
        return None


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


class RandomForestStrategy(TradingStrategy):
    """
    Estratégia baseada em Random Forest Classifier.

    Utiliza indicadores técnicos como features para prever se o preço subirá
    mais de 0.5% nas próximas 3 iterações.

    Args:
        retrain_interval (int): Número de iterações para retreinar o modelo (padrão: 50)
        min_data_points (int): Mínimo de pontos de dados para treinar (padrão: 100)
        prediction_threshold (float): Threshold de probabilidade para compra (padrão: 0.6)
    """

    def __init__(
        self,
        retrain_interval: int = 50,
        min_data_points: int = 100,
        prediction_threshold: float = 0.6,
    ):
        self.retrain_interval = int(retrain_interval)
        self.min_data_points = int(min_data_points)
        self.prediction_threshold = float(prediction_threshold)

        # Histórico de dados para features
        self.price_history: list[Decimal] = []
        self.volume_history: list[Decimal] = []
        self.timestamp_history: list[int] = []

        # Modelo e dados de treinamento
        self.model: RandomForestClassifier | None = None
        self.last_retrain_iteration = 0
        self.iteration_count = 0

        # Cache de features calculadas
        self._features_cache: list[dict] = []

    def initialize_historical_data(
        self,
        interval: int,
        start_datetime: datetime,
        symbol: str,
        public_api: MercadoBitcoinPublicAPI,
    ):
        """
        Inicializa a estratégia com dados históricos suficientes para treinar o modelo.

        Args:
            interval: Intervalo em segundos entre candles
            start_datetime: Data/hora de início da simulação
            symbol: Símbolo do ativo (ex: 'BTC-BRL')
            public_api: Instância da API pública para buscar dados históricos
        """
        # Calcular quantos dados históricos precisamos
        # Precisamos de pelo menos min_data_points + 20 (para indicadores) + 3 (para labels)
        required_points = max(self.min_data_points * 1.5 + 23, 150)

        # Calcular data de início para buscar dados históricos
        historical_start = start_datetime - timedelta(
            seconds=interval * required_points
        )

        try:
            # Buscar dados históricos de candles
            candles = public_api.get_candles(
                symbol,
                historical_start,
                start_datetime,
                IntervalResolution.to_resolution(interval),
            )

            # Inicializar históricos com os dados dos candles
            self.price_history = candles.close.copy()
            self.volume_history = candles.volume.copy()
            self.timestamp_history = candles.timestamp.copy()

            # Calcular features para todos os pontos históricos onde possível
            self._initialize_features_cache()

            # Tentar treinar o modelo inicial se tivermos dados suficientes
            if len(self._features_cache) >= self.min_data_points:
                success = self._train_model()
                if success:
                    print(
                        f"✅ Modelo Random Forest inicializado com {len(self._features_cache)} features"
                    )
                else:
                    print(
                        f"⚠️  Falha ao treinar modelo inicial com {len(self._features_cache)} features"
                    )
            else:
                print(
                    f"ℹ️  Dados insuficientes para treinar modelo inicial: {len(self._features_cache)}/{self.min_data_points}"
                )

        except Exception as e:
            print(f"❌ Erro ao inicializar dados históricos: {e}")
            # Em caso de erro, inicializar com listas vazias
            self.price_history = []
            self.volume_history = []
            self.timestamp_history = []
            self._features_cache = []

    def _initialize_features_cache(self):
        """Inicializa o cache de features com dados históricos"""
        self._features_cache = []

        # Salvar históricos originais
        original_price_history = self.price_history.copy()
        original_volume_history = self.volume_history.copy()

        # Calcular features para cada ponto onde temos dados suficientes
        for i in range(20, len(original_price_history)):  # Começar do 20º ponto
            # Temporariamente ajustar os históricos para calcular features até o ponto i
            self.price_history = original_price_history[: i + 1]
            self.volume_history = original_volume_history[: i + 1]

            # Calcular features para este ponto
            features = self._calculate_technical_indicators()
            if features is not None:
                self._features_cache.append(features)

        # Restaurar históricos originais
        self.price_history = original_price_history
        self.volume_history = original_volume_history

    def _calculate_technical_indicators(self) -> dict | None:
        """Calcula indicadores técnicos baseados no histórico de preços"""
        if len(self.price_history) < 20:  # Precisa de pelo menos 20 pontos
            return None

        prices = [float(p) for p in self.price_history]
        volumes = [float(v) for v in self.volume_history]

        # Converter para numpy arrays para cálculos
        price_array = np.array(prices)
        volume_array = np.array(volumes)

        # Calcular retornos
        returns = np.diff(price_array) / price_array[:-1]
        current_return = returns[-1] if len(returns) > 0 else 0

        # Médias móveis simples
        sma_5 = np.mean(price_array[-5:]) if len(price_array) >= 5 else price_array[-1]
        sma_10 = (
            np.mean(price_array[-10:]) if len(price_array) >= 10 else price_array[-1]
        )
        sma_20 = (
            np.mean(price_array[-20:]) if len(price_array) >= 20 else price_array[-1]
        )

        # RSI simplificado (baseado em retornos)
        if len(returns) >= 14:
            gains = np.where(returns[-14:] > 0, returns[-14:], 0)
            losses = np.where(returns[-14:] < 0, -returns[-14:], 0)
            avg_gain = np.mean(gains)
            avg_loss = np.mean(losses)
            rs = avg_gain / avg_loss if avg_loss != 0 else 100
            rsi = 100 - (100 / (1 + rs))
        else:
            rsi = 50  # Valor neutro

        # Volume médio
        volume_sma_5 = (
            np.mean(volume_array[-5:]) if len(volume_array) >= 5 else volume_array[-1]
        )

        # Volatilidade (desvio padrão dos retornos)
        volatility = np.std(returns[-10:]) if len(returns) >= 10 else 0

        # Preço atual vs médias (momentum)
        current_price = price_array[-1]
        price_vs_sma5 = (current_price - sma_5) / sma_5
        price_vs_sma10 = (current_price - sma_10) / sma_10
        price_vs_sma20 = (current_price - sma_20) / sma_20

        return {
            "sma_5": sma_5,
            "sma_10": sma_10,
            "sma_20": sma_20,
            "rsi": rsi,
            "volume_sma_5": volume_sma_5,
            "volatility": volatility,
            "current_return": current_return,
            "price_vs_sma5": price_vs_sma5,
            "price_vs_sma10": price_vs_sma10,
            "price_vs_sma20": price_vs_sma20,
            "current_price": current_price,
        }

    def _create_target_labels(self) -> list[int]:
        """Cria labels de target: 1 se preço subir >0.5% nas próximas 3 iterações"""
        if len(self.price_history) < 4:
            return []

        labels = []
        prices = [float(p) for p in self.price_history]

        # Para cada ponto (exceto os últimos 3), verifica se preço sobe >0.5% em 3 períodos
        for i in range(len(prices) - 3):
            current_price = prices[i]
            future_price = prices[i + 3]
            price_change = (future_price - current_price) / current_price

            # Label 1 se subir mais de 0.1%, senão 0
            label = 1 if price_change > 0.001 else 0
            labels.append(label)

        return labels

    def _should_retrain_model(self) -> bool:
        """Verifica se deve retreinar o modelo"""
        return (
            self.model is None
            or (self.iteration_count - self.last_retrain_iteration)
            >= self.retrain_interval
            or len(self._features_cache) < self.min_data_points
        )

    def _train_model(self) -> bool:
        """Treina o modelo Random Forest"""
        if len(self._features_cache) < self.min_data_points:
            return False

        # Preparar dados de treinamento
        features_list = []
        labels = self._create_target_labels()

        # Ajustar para usar apenas features que têm labels correspondentes
        # Como features começam a ser calculadas a partir do 20º ponto,
        # mas labels começam do 4º ponto, precisamos alinhar
        features_start_offset = 20 - 4  # 16 pontos de diferença

        if len(labels) <= features_start_offset:
            return False

        # Usar labels que correspondem às features disponíveis
        aligned_labels = labels[features_start_offset:]

        # Garantir que temos o mesmo número de features e labels
        min_length = min(len(self._features_cache), len(aligned_labels))
        valid_features = self._features_cache[:min_length]
        aligned_labels = aligned_labels[:min_length]

        if (
            len(valid_features) != len(aligned_labels)
            or len(aligned_labels) < self.min_data_points
        ):
            return False

        # Converter features para array
        feature_names = [
            "sma_5",
            "sma_10",
            "sma_20",
            "rsi",
            "volume_sma_5",
            "volatility",
            "current_return",
            "price_vs_sma5",
            "price_vs_sma10",
            "price_vs_sma20",
        ]

        for features in valid_features:
            feature_row = [features.get(name, 0) for name in feature_names]
            features_list.append(feature_row)

        X = np.array(features_list)
        y = np.array(aligned_labels)

        # Verificar se há variabilidade nos labels
        if len(np.unique(y)) < 2:
            return False

        # Treinar modelo
        self.model = RandomForestClassifier(
            n_estimators=100,
            random_state=42,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
        )

        try:
            self.model.fit(X, y)
            self.last_retrain_iteration = self.iteration_count
            return True
        except Exception:
            return False

    def _predict_price_movement(self) -> tuple[bool, float]:
        """Prediz movimento do preço usando o modelo treinado"""
        if self.model is None:
            return False, 0.0

        current_features = self._calculate_technical_indicators()
        if current_features is None:
            return False, 0.0

        # Preparar features para predição
        feature_names = [
            "sma_5",
            "sma_10",
            "sma_20",
            "rsi",
            "volume_sma_5",
            "volatility",
            "current_return",
            "price_vs_sma5",
            "price_vs_sma10",
            "price_vs_sma20",
        ]

        feature_row = [current_features.get(name, 0) for name in feature_names]
        X_pred = np.array([feature_row])

        try:
            # Obter probabilidades de predição
            probabilities = self.model.predict_proba(X_pred)[0]

            # Probabilidade da classe 1 (preço subir)
            prob_up = probabilities[1] if len(probabilities) > 1 else 0.0

            # Decidir se deve comprar baseado no threshold
            should_buy = prob_up > self.prediction_threshold

            return should_buy, prob_up
        except Exception:
            return False, 0.0

    def calculate_quantity(self, balance: Decimal, price: Decimal) -> Decimal:
        """Calcula quantidade baseada em 15% do saldo"""
        quantity = (balance * Decimal("0.15")) / price
        return quantity

    def on_market_refresh(
        self,
        ticker: TickerData,
        balance: Decimal,
        current_position: Position | None,
        position_history: list[Position],
    ) -> OrderSignal | None:
        """Processa novos dados de mercado e toma decisões de trading"""

        # Atualizar históricos
        self.price_history.append(ticker.last)
        self.volume_history.append(ticker.vol)
        self.timestamp_history.append(ticker.date)
        self.iteration_count += 1

        # Manter apenas os últimos 200 pontos para eficiência
        max_history = 200
        if len(self.price_history) > max_history:
            self.price_history = self.price_history[-max_history:]
            self.volume_history = self.volume_history[-max_history:]
            self.timestamp_history = self.timestamp_history[-max_history:]

        # Calcular features técnicas
        features = self._calculate_technical_indicators()
        if features is not None:
            self._features_cache.append(features)

            # Manter cache de features sincronizado
            if len(self._features_cache) > max_history:
                self._features_cache = self._features_cache[-max_history:]

        # Retreinar modelo se necessário
        if self._should_retrain_model():
            self._train_model()

        # Tomar decisões de trading
        if not current_position:
            # Sem posição - considerar compra
            if self.model is not None and len(self.price_history) >= 20:
                should_buy, confidence = self._predict_price_movement()

                if should_buy:
                    return OrderSignal(
                        OrderSide.BUY, self.calculate_quantity(balance, ticker.last)
                    )
        else:
            # Com posição - considerar venda
            # Estratégia simples: vender se modelo prediz queda ou após 10 iterações
            if self.model is not None:
                should_buy, confidence = self._predict_price_movement()

                # Vender se confiança de alta for baixa (< 0.4) ou se posição está há muito tempo aberta
                position_age = len(self.price_history) - getattr(
                    current_position, "_entry_iteration", len(self.price_history)
                )

                if confidence < 0.4 or position_age > 10:
                    return OrderSignal(
                        OrderSide.SELL, current_position.entry_order.quantity
                    )

        return None
