from .trading_strategy import IterationStrategy, TradingStrategy


class NotImplementedStrategy(Exception):
    pass


STRATEGIES = {
    "iteration": IterationStrategy,
}


def get_strategy_cls(strategy: str) -> type[TradingStrategy]:
    """Retorna a classe da estratégia correspondente"""
    if strategy not in STRATEGIES:
        raise NotImplementedStrategy(f"Estratégia {strategy} não implementada")
    return STRATEGIES[strategy]
