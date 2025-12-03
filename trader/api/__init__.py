"""
Módulo de interfaces da API do Mercado Bitcoin e Jupiter.
"""

from .base_api import PrivateAPIBase, PublicAPIBase
from .fake_private_api import FakeMercadoBitcoinPrivateAPI
from .jupiter_adapter import (
    FakeJupiterPrivateAPI,
    JupiterPrivateAPI,
    JupiterPublicAPIAdapter,
)
from .jupiter_public_api import SOLANA_TOKENS, JupiterPublicAPI
from .private_api import MercadoBitcoinPrivateAPI, UnauthorizedError
from .public_api import MercadoBitcoinPublicAPI

__all__ = [
    # Base interfaces
    "PublicAPIBase",
    "PrivateAPIBase",
    # Mercado Bitcoin
    "MercadoBitcoinPublicAPI",
    "MercadoBitcoinPrivateAPI",
    "FakeMercadoBitcoinPrivateAPI",
    "UnauthorizedError",
    # Jupiter (APIs nativas)
    "JupiterPublicAPI",
    "JupiterPrivateAPI",
    "SOLANA_TOKENS",
    # Jupiter (Adaptadores compatíveis)
    "JupiterPublicAPIAdapter",
    "FakeJupiterPrivateAPI",
]
