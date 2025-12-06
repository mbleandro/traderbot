from .trading_strategy import (
    DynamicTargetStrategy,
    RandomStrategy,
    TargetValueStrategy,
    TradingStrategy,
)


class NotImplementedStrategy(Exception):
    pass


STRATEGIES = {
    "random": RandomStrategy,
    "target_value": TargetValueStrategy,
    "dynamic_target": DynamicTargetStrategy,
}


def get_strategy_cls(strategy: str) -> type[TradingStrategy]:
    """Retorna a classe da estratégia correspondente"""
    if strategy not in STRATEGIES:
        raise NotImplementedStrategy(f"Estratégia {strategy} não implementada")
    return STRATEGIES[strategy]
