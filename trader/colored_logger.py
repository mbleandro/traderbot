import logging
import sys

from colorama import Back, Fore, Style, init

# Inicializar colorama para compatibilidade com Windows
init(autoreset=True)


class ColoredFormatter(logging.Formatter):
    """Formatter personalizado que adiciona cores aos logs"""

    # Definir cores para cada nível de log
    COLORS = {
        "DEBUG": Fore.CYAN,
        "INFO": Fore.GREEN,
        "WARNING": Fore.YELLOW,
        "ERROR": Fore.RED,
        "CRITICAL": Fore.RED + Back.WHITE + Style.BRIGHT,
    }

    # Cores específicas para diferentes tipos de mensagem
    MESSAGE_COLORS = {
        "price": Fore.BLUE + Style.BRIGHT,
        "buy": Fore.GREEN + Style.BRIGHT,
        "sell": Fore.RED + Style.BRIGHT,
        "profit": Fore.GREEN,
        "loss": Fore.RED,
        "position": Fore.MAGENTA,
        "balance": Fore.CYAN,
        "signal": Fore.YELLOW + Style.BRIGHT,
        "order": Fore.WHITE + Style.BRIGHT,
        "error": Fore.RED + Style.BRIGHT,
        "success": Fore.GREEN + Style.BRIGHT,
        "warning": Fore.YELLOW,
        "info": Fore.WHITE,
    }

    def __init__(self, fmt=None, datefmt=None):
        super().__init__()
        self.fmt = fmt or "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        self.datefmt = datefmt or "%Y-%m-%d %H:%M:%S"

    def format(self, record):
        # Obter cor do nível
        level_color = self.COLORS.get(record.levelname, Fore.WHITE)

        # Colorir a mensagem baseado no conteúdo
        message = record.getMessage()
        colored_message = self._colorize_message(message)

        # Criar o log formatado
        log_time = self.formatTime(record, self.datefmt)

        # Aplicar cores aos diferentes componentes
        formatted_log = (
            f"{Fore.WHITE}{log_time}{Style.RESET_ALL} - "
            f"{Fore.BLUE}{record.name}{Style.RESET_ALL} - "
            f"{level_color}{record.levelname}{Style.RESET_ALL} - "
            f"{colored_message}{Style.RESET_ALL}"
        )

        return formatted_log

    def _colorize_message(self, message: str) -> str:
        """Aplica cores específicas baseadas no conteúdo da mensagem"""
        message_lower = message.lower()

        # Detectar tipo de mensagem e aplicar cor apropriada
        if False:
            pass

        elif any(keyword in message_lower for keyword in ["erro", "error", "falha"]):
            return self.MESSAGE_COLORS["error"] + message
        elif any(keyword in message_lower for keyword in ["sucesso", "success"]):
            return self.MESSAGE_COLORS["success"] + message
        elif any(
            keyword in message_lower for keyword in ["aviso", "warning", "atenção"]
        ):
            return self.MESSAGE_COLORS["warning"] + message

        elif any(
            keyword in message_lower for keyword in ["compra", "buy", "comprando"]
        ):
            return self.MESSAGE_COLORS["buy"] + message
        elif any(keyword in message_lower for keyword in ["venda", "sell", "vendendo"]):
            return self.MESSAGE_COLORS["sell"] + message

        elif any(keyword in message_lower for keyword in ["lucro", "profit", "ganho"]):
            if any(keyword in message_lower for keyword in ["negativo", "-", "perda"]):
                return self.MESSAGE_COLORS["loss"] + message
            return self.MESSAGE_COLORS["profit"] + message
        elif any(keyword in message_lower for keyword in ["posição", "position"]):
            return self.MESSAGE_COLORS["position"] + message
        elif any(
            keyword in message_lower for keyword in ["saldo", "balance", "brl", "btc"]
        ):
            return self.MESSAGE_COLORS["balance"] + message
        elif any(
            keyword in message_lower for keyword in ["sinal", "signal", "detectado"]
        ):
            return self.MESSAGE_COLORS["signal"] + message
        elif any(
            keyword in message_lower for keyword in ["ordem", "order", "executada"]
        ):
            return self.MESSAGE_COLORS["order"] + message
        elif any(keyword in message_lower for keyword in ["preço", "price", "r$"]):
            return self.MESSAGE_COLORS["price"] + message
        else:
            return self.MESSAGE_COLORS["info"] + message


class TradingLogger:
    """Classe para configurar e gerenciar logging colorido para trading"""

    def __init__(self, name: str = "TradingBot", level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        # Remover handlers existentes para evitar duplicação
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # Criar handler para console
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)

        # Aplicar formatter colorido
        colored_formatter = ColoredFormatter()
        console_handler.setFormatter(colored_formatter)

        # Adicionar handler ao logger
        self.logger.addHandler(console_handler)

        # Evitar propagação para o logger raiz
        self.logger.propagate = False

    def get_logger(self) -> logging.Logger:
        """Retorna o logger configurado"""
        return self.logger

    # Métodos de conveniência com cores específicas
    def log_price(self, symbol: str, price: float):
        """Log específico para preços"""
        self.logger.info(
            "__________________________________________________________________"
        )
        self.logger.info(f"💰 Preço atual {symbol}: R$ {price:.2f}")

    def log_position_signal(self, side: str, price: float):
        """Log específico para sinais de posição"""
        if side == "buy":
            self.logger.info(f"📈 Sinal de COMPRA detectado - Preço: R$ {price:.2f}")
        elif side == "sell":
            self.logger.info(f"📉 Sinal de VENDA detectado - Preço: R$ {price:.2f}")

    def log_order_placed(self, order_id: str, side: str, price: float, quantity: float):
        """Log específico para ordens colocadas"""
        if side == "buy":
            self.logger.info(
                f"✅ Ordem de COMPRA executada ({order_id}) - Preço: R$ {price:.2f}, Quantidade: {quantity:.8f}"
            )
        elif side == "sell":
            self.logger.info(
                f"✅ Ordem de VENDA executada ({order_id}) - Preço: R$ {price:.2f}, Quantidade: {quantity:.8f}"
            )

    def log_position(self, side: str, quantity: float, entry_price: float):
        """Log específico para posições"""
        self.logger.info(
            f"📊 Posição atual: {side.upper()} {quantity:.8f} @ R$ {entry_price:.2f}"
        )

    def log_pnl(self, unrealized_pnl: float, realized_pnl: float):
        """Log específico para PnL"""
        unrealized_emoji = "📈" if unrealized_pnl >= 0 else "📉"
        realized_emoji = "💰" if realized_pnl >= 0 else "💸"

        self.logger.info(
            f" ↳ {unrealized_emoji} PnL não realizado: R$ {unrealized_pnl:.2f}"
        )
        self.logger.info(
            f" ↳ {realized_emoji} PnL total realizado: R$ {realized_pnl:.2f}"
        )

    def log_balance(self, brl_balance: float, btc_balance: float):
        """Log específico para saldos"""
        self.logger.info(
            f"💳 Saldos - BRL: R$ {brl_balance:.2f}, BTC: {btc_balance:.8f}"
        )

    def log_bot_start(self, symbol: str):
        """Log específico para início do bot"""
        self.logger.info(f"🚀 Bot iniciado para {symbol}")

    def log_bot_stop(self):
        """Log específico para parada do bot"""
        self.logger.info("🛑 Bot parado")

    def log_error(self, message: str, exception: Exception | None = None):
        """Log específico para erros"""
        if exception:
            self.logger.error(f"❌ {message}: {str(exception)}")
        else:
            self.logger.error(f"❌ {message}")

    def log_warning(self, message: str):
        """Log específico para avisos"""
        self.logger.warning(f"⚠️ {message}")


def setup_colored_logging(
    name: str = "TradingBot", level: int = logging.INFO
) -> logging.Logger:
    """Função de conveniência para configurar logging colorido"""
    trading_logger = TradingLogger(name, level)
    return trading_logger.get_logger()


def get_trading_logger(name: str = "TradingBot") -> TradingLogger:
    """Função de conveniência para obter um TradingLogger"""
    return TradingLogger(name)
