from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, getcontext
from statistics import mean
from typing import Any, Dict, List

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table

from trader.models.order import Order, OrderSide
from trader.models.position import Position, PositionType
from trader.models.public_data import TickerData

# Precisão para cálculos financeiros
getcontext().prec = 28
getcontext().rounding = ROUND_HALF_UP

console = Console()


class ReportDataArgument:
    def __init__(self, title, format):
        self.title = title
        self.format = format


def Argument(title, format=lambda x: f"{x}") -> Any:
    return ReportDataArgument(title, format)


class ReportData:
    @abstractmethod
    def from_bot_data(
        self, ticker_history: List[TickerData], position_history: List[Position]
    ):
        raise NotImplementedError

    @abstractmethod
    def title(self) -> str:
        raise NotImplementedError

    def result(self) -> str:
        raise NotImplementedError


@dataclass
class Overview(ReportData):
    periodo: str = Argument(title="Período de execução", format=lambda x: f"{x}")
    variacao_preco: Decimal = Argument(
        title="Variação de preço", format=lambda x: f"R$ {x:.2f}"
    )
    total_operacoes: int = Argument(
        title="Total de operações", format=lambda x: f"{x:,}"
    )
    operacoes_lucrativas: int = Argument(
        title="Operações lucrativas", format=lambda x: f"{x:,}"
    )
    operacoes_perdedoras: int = Argument(
        title="Operações perdedoras", format=lambda x: f"{x:,}"
    )
    pnl: Decimal = Argument(title="PnL total", format=lambda x: f"R$ {x:.2f}")

    @classmethod
    def from_bot_data(
        cls, ticker_history: List[TickerData], position_history: List[Position]
    ):
        return cls(
            periodo=(f"{ticker_history[0].timestamp} → {ticker_history[-1].timestamp}"),
            variacao_preco=(ticker_history[-1].last - ticker_history[0].last),
            total_operacoes=len(position_history),
            operacoes_lucrativas=sum(
                1 for pos in position_history if pos.realized_pnl > 0
            ),
            operacoes_perdedoras=sum(
                1 for pos in position_history if pos.realized_pnl < 0
            ),
            pnl=cls.get_total_realized_pnl(position_history)
            + cls.get_unrealized_pnl(position_history, ticker_history),
        )

    @staticmethod
    def get_total_realized_pnl(position_history: List[Position]) -> Decimal:
        return sum(
            (position_history[i].realized_pnl for i in range(len(position_history))),
            Decimal("0"),
        )

    @staticmethod
    def get_unrealized_pnl(
        position_history: List[Position], ticker_history: List[TickerData]
    ) -> Decimal:
        last_pos = position_history[-1]
        if getattr(last_pos, "exit_order", None) is None:
            return last_pos.unrealized_pnl(ticker_history[-1].last)
        return Decimal("0")

    def title(self) -> str:
        return "Resumo Geral"

    def result(self) -> str:
        return (
            "Bullish!" if self.variacao_preco > 0 else "Bearish!"
        )  # bullish é alta, bearish é baixa


@dataclass
class TradeStats(ReportData):
    avg_win: Decimal = Argument(
        title="Lucro médio por trade", format=lambda x: f"R$ {x:.2f}"
    )
    avg_loss: Decimal = Argument(
        title="Perda média por trade", format=lambda x: f"R$ {x:.2f}"
    )
    payoff: Decimal = Argument(title="Payoff Ratio", format=lambda x: f"{x:.2f}")
    expectancy: Decimal = Argument(
        title="Expectância (por trade)", format=lambda x: f"R$ {x:.2f}"
    )
    greatest_gain: Decimal = Argument(
        title="Maior ganho (trade)", format=lambda x: f"R$ {x:.2f}"
    )
    greatest_loss: Decimal = Argument(
        title="Maior perda (trade)", format=lambda x: f"R$ {x:.2f}"
    )

    @classmethod
    def from_bot_data(cls, position_history: List[Position]):
        wins = [pos.realized_pnl for pos in position_history if pos.realized_pnl > 0]
        losses = [pos.realized_pnl for pos in position_history if pos.realized_pnl < 0]

        return cls(
            avg_win=mean(wins),
            avg_loss=mean(losses),
            payoff=(
                abs(mean(wins)) / abs(mean(losses))
                if mean(losses) != 0
                else Decimal("0")
            ),
            expectancy=mean(wins + losses),
            greatest_gain=max(wins, default=Decimal("0")),
            greatest_loss=min(losses, default=Decimal("0")),
        )

    def title(self) -> str:
        return "Estatísticas de Trade"

    def result(self) -> str:
        return "Tá legal!" if self.avg_win > self.avg_loss else "Tá ruim!"


@dataclass
class RiskStats(ReportData):
    capital_curve: List[Decimal] = Argument(
        title="Curva de capital (final)", format=lambda x: f"R$ {x[-1]:.2f}"
    )
    max_drawdown: Decimal = Argument(
        title="Max Drawdown", format=lambda x: f"R$ {x:.2f}"
    )
    volatility: Decimal = Argument(
        title="Volatilidade (desvio padrão)", format=lambda x: f"R$ {x:.2f}"
    )
    sharpe: Decimal = Argument(title="Sharpe (aprx)", format=lambda x: f"{x:.2f}")

    @classmethod
    def from_bot_data(cls, position_history: List[Position]):
        capital_curve = cls._build_capital_curve(position_history)
        volatility = cls._desvio_padrao([pos.realized_pnl for pos in position_history])
        # Sharpe: mean / volatility scaled by sqrt(N)
        mean_r = mean([pos.realized_pnl for pos in position_history])
        sharpe = Decimal("0")
        n = len(position_history)
        if volatility != 0 and n > 0:
            sharpe = (mean_r / volatility) * Decimal(n).sqrt()

        return cls(
            capital_curve=capital_curve,
            max_drawdown=cls._calc_max_drawdown(capital_curve),
            volatility=volatility,
            sharpe=sharpe,
        )

    @staticmethod
    def _desvio_padrao(
        values: List[Decimal],
    ) -> Decimal:
        # amostral (denominator n-1). retorna 0 se n < 2
        n = len(values)
        if n < 2:
            return Decimal("0")
        _mean = mean(values)
        # variance as Decimal
        var = sum(((v - _mean) ** 2 for v in values), Decimal("0")) / Decimal(n - 1)
        # sqrt variance with Decimal
        return var.sqrt()

    @staticmethod
    def _build_capital_curve(position_history) -> List[Decimal]:
        c = Decimal("0")
        curve = []
        for pos in position_history:
            c += pos.realized_pnl
            curve.append(c)
        return curve

    @staticmethod
    def _calc_max_drawdown(curve: List[Decimal]) -> Decimal:
        if not curve:
            return Decimal("0")
        peak = curve[0]
        max_dd = Decimal("0")
        for value in curve:
            if value > peak:
                peak = value
            dd = peak - value
            if dd > max_dd:
                max_dd = dd
        return max_dd

    def title(self) -> str:
        return "Estatísticas de Risco"

    def result(self) -> str:
        return ""


@dataclass
class HoldVsTrade(ReportData):
    hold_pnl: Decimal = Argument(title="PnL HOLD", format=lambda x: f"R$ {x:.2f}")
    trade_pnl: Decimal = Argument(title="PnL TRADING", format=lambda x: f"R$ {x:.2f}")

    @classmethod
    def from_bot_data(
        cls, ticker_history: List[TickerData], position_history: List[Position]
    ):
        trade_pnl = Overview.from_bot_data(ticker_history, position_history).pnl

        # Cria uma posição de HOLD fake
        position_hold_history = [
            Position(
                type=PositionType.LONG,
                entry_order=Order(
                    order_id="hold",
                    symbol="BTC-BRL",
                    quantity=position_history[0].entry_order.quantity,
                    price=ticker_history[0].last,
                    side=OrderSide.BUY,
                    timestamp=ticker_history[0].timestamp,
                ),
                exit_order=None,
            )
        ]
        hold_pnl = Overview.from_bot_data(ticker_history, position_hold_history).pnl
        return cls(hold_pnl=hold_pnl, trade_pnl=trade_pnl)

    def title(self) -> str:
        return "Análise HOLD vs TRADING"

    def result(self) -> str:
        winner = "TRADING" if self.trade_pnl > self.hold_pnl else "HOLD"
        return f"{winner} foi melhor por R$ {abs(self.trade_pnl - self.hold_pnl):.2f}"


@dataclass
class HourlyPnLDistribution(ReportData):
    """Distribuição de lucros e prejuízos por horário do dia"""

    hourly_pnl: Dict[int, Decimal]
    best_hour: int = Argument(title="Melhor horário", format=lambda x: f"{x:02d}:00")
    worst_hour: int = Argument(title="Pior horário", format=lambda x: f"{x:02d}:00")
    total_trades_by_hour: Dict[int, int] = Argument(
        title="Trades por hora", format=lambda x: f"{mean(x.values())} media"
    )

    @classmethod
    def from_bot_data(
        cls, ticker_history: List[TickerData], position_history: List[Position]
    ):
        # Inicializa dicionários para cada hora (0-23)
        hourly_pnl = defaultdict(Decimal)
        hourly_trades = defaultdict(int)

        # Processa cada posição fechada
        for position in position_history:
            if position.exit_order:  # Apenas posições fechadas
                # Usa o horário da ordem de saída
                hour = position.exit_order.timestamp.hour
                hourly_pnl[hour] += position.realized_pnl
                hourly_trades[hour] += 1

        # Converte para dicionários normais com todas as 24 horas
        full_hourly_pnl = {
            hour: hourly_pnl.get(hour, Decimal("0")) for hour in range(24)
        }
        full_hourly_trades = {hour: hourly_trades.get(hour, 0) for hour in range(24)}

        # Encontra melhor e pior horário
        best_hour = max(full_hourly_pnl.keys(), key=lambda h: full_hourly_pnl[h])
        worst_hour = min(full_hourly_pnl.keys(), key=lambda h: full_hourly_pnl[h])

        return cls(
            hourly_pnl=full_hourly_pnl,
            best_hour=best_hour,
            worst_hour=worst_hour,
            total_trades_by_hour=full_hourly_trades,
        )

    def title(self) -> str:
        return "Distribuição de PnL por Horário"

    def result(self) -> str:
        total_positive_hours = sum(1 for pnl in self.hourly_pnl.values() if pnl > 0)
        return f"{total_positive_hours}/24 horários com resultado positivo"


class ReportBase(ABC):
    """Base para relatórios de backtest"""

    @abstractmethod
    def generate_report(self):
        raise NotImplementedError

    def add_position_history(self, position_history: List[Position]):
        self.position_history = position_history

    def add_ticker_history(self, ticker_history: List[TickerData]):
        self.ticker_history = ticker_history


class ReportTerminal(ReportBase):
    """Relatório no terminal"""

    def generate_report(self):
        self.show_reports(self.generate_report_data())

    def generate_report_data(self) -> list[ReportData]:
        return [
            Overview.from_bot_data(self.ticker_history, self.position_history),
            TradeStats.from_bot_data(self.position_history),
            RiskStats.from_bot_data(self.position_history),
            HoldVsTrade.from_bot_data(self.ticker_history, self.position_history),
            HourlyPnLDistribution.from_bot_data(
                self.ticker_history, self.position_history
            ),
        ]

    def show_reports(self, reports: List[ReportData]):
        tables = []
        for report in reports:
            table = Table("Métrica", "Valor", title=report.title())
            for field in report.__dataclass_fields__.values():  # type: ignore
                if isinstance(field.default, ReportDataArgument):
                    value = getattr(report, field.name)
                    value = field.default.format(value)
                    table.add_row(
                        field.default.title,
                        value,
                    )
            tables.append(table)
        console.print(
            Panel(
                Group(*tables),
                title="[bold green]RELATÓRIO DE EXECUÇÃO[/bold green]",
            )
        )
