from abc import ABC, abstractmethod
from decimal import Decimal

from rich import print
from rich.console import Console
from rich.table import Table

console = Console()


class ReportBase(ABC):
    """Classe base para relatórios de trading bot"""

    @abstractmethod
    def generate_report(self):
        """Gera relatório"""
        pass

    def add_position_history(self, position_history: list):
        """Adiciona histórico de posições"""
        self.position_history = position_history

    def add_ticker_history(self, ticker_history: list):
        """Adiciona histórico de posições"""
        self.ticker_history = ticker_history


class ReportTerminal(ReportBase):
    """Relatório no terminal"""

    def generate_report(self, model: str = "summary"):
        """Gera relatório no terminal"""
        if model == "summary":
            self._generate_summary_report()

    def _generate_summary_report(self):
        """Gera relatório de resumo"""
        console.print("========== RELATÓRIO DE EXECUÇÃO ==========")

        # self.trading_logger.log_unrealized_pnl(float(unrealized_pnl))
        # self.trading_logger.log_realized_pnl(float(realized_pnl))
        if len(self.ticker_history) < 1 or len(self.position_history) < 1:
            print("Dados insuficientes para gerar relatório")
            return

        price_variation = self.ticker_history[-1].last - self.ticker_history[0].last
        profitable_trades = sum(
            1 for pos in self.position_history if pos.realized_pnl > 0
        )

        table = Table("Nome", "Valor")
        table.add_row("Variação de Preço", f"R$ {price_variation:.2f}")
        table.add_row("Total de operações realizadas", str(len(self.position_history)))
        table.add_row(
            "Operações lucrativas", f"{profitable_trades}/{len(self.position_history)}"
        )

        console.print(table)

        first_position_entry_price = self.position_history[0].entry_order.price
        first_position_quantity = self.position_history[0].entry_order.quantity
        final_price = self.ticker_history[-1].last

        initial_investment = first_position_entry_price * first_position_quantity

        table = Table("Nome", "Valor")
        table.add_row("Investimento inicial", f"R$ {initial_investment:.2f}")
        table.add_row("Preço inicial", f"R$ {first_position_entry_price:.2f}")
        table.add_row("Preço final", f"R$ {final_price:.2f}")
        console.print(table)

        console.print("========== ANÁLISE HOLD vs TRADING ==========")
        hold_pnl = (final_price - first_position_entry_price) * first_position_quantity
        hold_return_pct = (hold_pnl / initial_investment) * 100
        actual_pnl = self.get_total_realized_pnl() + self.get_unrealized_pnl()
        actual_return_pct = (actual_pnl / initial_investment) * 100
        table = Table("Estratégia", "Retorno (R$)", "Retorno (%)")
        table.add_row("HOLD", f"R$ {hold_pnl:.2f}", f"{hold_return_pct:+.2f}%")
        table.add_row("TRADING", f"R$ {actual_pnl:.2f}", f"{actual_return_pct:+.2f}%")
        console.print(table)

        difference = (hold_pnl - actual_pnl).quantize(Decimal("0.01"))
        if abs(difference) > 0:
            print(
                f"{'TRADING' if difference < 0 else 'HOLD'} foi MELHOR por R$ {abs(difference):.2f}"
            )
        else:
            print("EMPATE: Ambas estratégias tiveram o mesmo resultado")

    def get_total_realized_pnl(self) -> Decimal:
        """Retorna o PnL total realizado"""
        return Decimal(str(sum(pos.realized_pnl for pos in self.position_history)))

    def get_unrealized_pnl(self) -> Decimal:
        """Retorna o PnL não realizado da posição atual"""
        if self.position_history[-1].exit_order is None:
            return self.position_history[-1].unrealized_pnl(
                self.ticker_history[-1].last
            )
        return Decimal("0.0")
