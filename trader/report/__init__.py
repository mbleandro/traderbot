from abc import ABC, abstractmethod
from decimal import Decimal


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
        print("📊 ===== RELATÓRIO DE EXECUÇÃO =====")

        realized_pnl = self.get_total_realized_pnl()
        unrealized_pnl = self.get_unrealized_pnl()

        # self.trading_logger.log_unrealized_pnl(float(unrealized_pnl))
        # self.trading_logger.log_realized_pnl(float(realized_pnl))

        if len(self.ticker_history) > 1:
            price_variation = self.ticker_history[-1].last - self.ticker_history[0].last
            print(f"📈 Variação do preço: R$ {price_variation:.2f}")

        # Mostrar histórico de posições
        if self.position_history:
            print(f"📋 Total de operações realizadas: {len(self.position_history)}")
            profitable_trades = sum(
                1 for pos in self.position_history if pos.realized_pnl > 0
            )
            print(
                f"✅ Operações lucrativas: {profitable_trades}/{len(self.position_history)}"
            )

        # Análise de "Hold Strategy" - quanto teria ganhado mantendo a primeira posição
        self._show_hold_strategy_analysis()

        print("📊 ===========================")

    def _show_hold_strategy_analysis(self):
        """Mostra análise de quanto teria ganhado com estratégia de hold"""

        if self.position_history:
            first_position_entry_price = self.position_history[0].entry_order.price
            first_position_quantity = self.position_history[0].entry_order.quantity
            final_price = self.ticker_history[-1].last
        else:
            print("📊 Análise de Hold Strategy: Dados insuficientes")
            return

        # Calcular PnL se tivesse mantido a primeira posição
        hold_pnl = (final_price - first_position_entry_price) * first_position_quantity

        # Calcular PnL real do bot
        actual_pnl = self.get_total_realized_pnl() + self.get_unrealized_pnl()

        # Calcular percentuais de retorno
        initial_investment = first_position_entry_price * first_position_quantity
        hold_return_pct = (hold_pnl / initial_investment) * 100
        actual_return_pct = (actual_pnl / initial_investment) * 100

        difference = hold_pnl - actual_pnl

        print("🔍 ===== ANÁLISE HOLD vs TRADING =====")
        print(f"💰 Investimento inicial: R$ {initial_investment:.2f}")
        print(f"💰 Preço inicial: R$ {first_position_entry_price:.2f}")
        print(f"💰 Preço final: R$ {final_price:.2f}")

        # Log colorido baseado no resultado
        if hold_pnl > 0:
            print(
                f"💰 PnL se tivesse mantido (HOLD): R$ {hold_pnl:.2f} ({hold_return_pct:+.2f}%)"
            )
        else:
            print(
                f"💸 PnL se tivesse mantido (HOLD): R$ {hold_pnl:.2f} ({hold_return_pct:+.2f}%)"
            )

        if actual_pnl > 0:
            print(
                f"💰 PnL real do bot (TRADING): R$ {actual_pnl:.2f} ({actual_return_pct:+.2f}%)"
            )
        else:
            print(
                f"💸 PnL real do bot (TRADING): R$ {actual_pnl:.2f} ({actual_return_pct:+.2f}%)"
            )

        # Comparação final
        if difference > 0:
            print(f"📈 HOLD teria sido MELHOR por R$ {difference:.2f}")
            print(
                f"💡 Estratégia de hold teria superado o trading em {abs(difference):.2f} reais"
            )
        elif difference < 0:
            print(f"📉 TRADING foi MELHOR por R$ {abs(difference):.2f}")
            print(f"🎯 Bot superou a estratégia de hold em {abs(difference):.2f} reais")
        else:
            print("⚖️ EMPATE: Ambas estratégias tiveram o mesmo resultado")

        print("🔍 ================================")

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
