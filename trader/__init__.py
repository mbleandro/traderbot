from .trading_strategy import IterationStrategy, RandomForestStrategy, TradingStrategy


class NotImplementedStrategy(Exception):
    pass


STRATEGIES = {
    "iteration": IterationStrategy,
    "randomforest": RandomForestStrategy,
}


def get_strategy_cls(strategy: str) -> type[TradingStrategy]:
    """Retorna a classe da estratégia correspondente"""
    if strategy not in STRATEGIES:
        raise NotImplementedStrategy
    return STRATEGIES[strategy]
