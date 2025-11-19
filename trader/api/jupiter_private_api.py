"""
Interface privada da API Jupiter (Solana DEX Aggregator).
Esta interface requer uma wallet Solana para assinar e enviar transações.
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..models.jupiter_data import JupiterQuoteResponse, JupiterSwapResponse


class JupiterTransactionError(Exception):
    """Exceção para erros de transação"""

    pass


class JupiterPrivateAPIBase(ABC):
    """
    Interface abstrata da API privada da Jupiter.
    """

    @abstractmethod
    def get_swap_transaction(
        self,
        quote_response: JupiterQuoteResponse,
        user_public_key: str,
        wrap_unwrap_sol: bool = True,
        fee_account: Optional[str] = None,
        compute_unit_price_micro_lamports: Optional[int] = None,
    ) -> JupiterSwapResponse:
        """Obtém transação serializada para executar o swap"""
        ...

    @abstractmethod
    def execute_swap(
        self,
        swap_transaction: str,
        wallet_private_key: str,
    ) -> str:
        """Executa o swap e retorna o transaction ID"""
        ...


class JupiterPrivateAPI(JupiterPrivateAPIBase):
    """
    Interface privada da API Jupiter.
    Requer wallet Solana - ideal para executar swaps.
    """

    def __init__(self, rpc_url: str, use_pro: bool = False):
        """
        Inicializa a API privada da Jupiter.

        Args:
            rpc_url: URL do RPC endpoint da Solana
            use_pro: Se True, usa a API Pro (requer API key)
        """
        if use_pro:
            self.base_url = "https://quote-api.jup.ag/v6"
        else:
            self.base_url = "https://quote-api.jup.ag/v6"

        self.rpc_url = rpc_url
        self.session = requests.Session()
        self.logger = logging.getLogger(__name__)

        # Headers padrão
        self.session.headers.update(
            {
                "Content-Type": "application/json",
            }
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(JupiterTransactionError),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
        reraise=True,
    )
    def _make_request(
        self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Faz requisição para a API com retry automático"""
        url = f"{self.base_url}{endpoint}"
        body = json.dumps(data) if data else None

        headers = {
            "Content-Type": "application/json",
        }

        response = self.session.request(method, url, headers=headers, data=body)

        if response.status_code != 200:
            error_msg = f"Erro na requisição {url}: status={response.status_code} response={response.text}"
            self.logger.error(error_msg)
            raise JupiterTransactionError(error_msg)

        return response.json()

    def get_swap_transaction(
        self,
        quote_response: JupiterQuoteResponse,
        user_public_key: str,
        wrap_unwrap_sol: bool = True,
        fee_account: Optional[str] = None,
        compute_unit_price_micro_lamports: Optional[int] = None,
        use_dynamic_slippage: bool = False,
        dynamic_slippage_max_bps: Optional[int] = None,
    ) -> JupiterSwapResponse:
        """
        Obtém transação serializada para executar o swap.

        Args:
            quote_response: Resposta da API de quote
            user_public_key: Chave pública do usuário (base58)
            wrap_unwrap_sol: Auto wrap/unwrap SOL (padrão: True)
            fee_account: Conta para receber fees (opcional)
            compute_unit_price_micro_lamports: Priority fee em micro lamports
            use_dynamic_slippage: Usar slippage dinâmico
            dynamic_slippage_max_bps: Slippage máximo em bps para slippage dinâmico

        Returns:
            JupiterSwapResponse: Transação serializada
        """
        # Converte o quote_response para dict
        quote_dict = {
            "inputMint": quote_response.input_mint,
            "inAmount": quote_response.in_amount,
            "outputMint": quote_response.output_mint,
            "outAmount": quote_response.out_amount,
            "otherAmountThreshold": quote_response.other_amount_threshold,
            "swapMode": quote_response.swap_mode,
            "slippageBps": quote_response.slippage_bps,
            "platformFee": quote_response.platform_fee,
            "priceImpactPct": quote_response.price_impact_pct,
            "routePlan": [
                {
                    "swapInfo": {
                        "ammKey": rp.swap_info.amm_key,
                        "label": rp.swap_info.label,
                        "inputMint": rp.swap_info.input_mint,
                        "outputMint": rp.swap_info.output_mint,
                        "inAmount": rp.swap_info.in_amount,
                        "outAmount": rp.swap_info.out_amount,
                        "feeAmount": rp.swap_info.fee_amount,
                        "feeMint": rp.swap_info.fee_mint,
                    },
                    "percent": rp.percent,
                }
                for rp in quote_response.route_plan
            ],
        }

        if quote_response.context_slot is not None:
            quote_dict["contextSlot"] = quote_response.context_slot
        if quote_response.time_taken is not None:
            quote_dict["timeTaken"] = quote_response.time_taken

        data: Dict[str, Any] = {
            "quoteResponse": quote_dict,
            "userPublicKey": user_public_key,
            "wrapAndUnwrapSol": wrap_unwrap_sol,
        }

        if fee_account:
            data["feeAccount"] = fee_account

        if compute_unit_price_micro_lamports:
            data["prioritizationFeeLamports"] = {
                "priorityLevelWithMaxLamports": {
                    "maxLamports": compute_unit_price_micro_lamports,
                    "priorityLevel": "veryHigh",
                }
            }

        if use_dynamic_slippage and dynamic_slippage_max_bps:
            data["dynamicSlippage"] = {"maxBps": dynamic_slippage_max_bps}

        response = self._make_request("POST", "/swap", data=data)

        return JupiterSwapResponse.from_dict(response)

    def execute_swap(
        self,
        swap_transaction: str,
        wallet_private_key: str,
    ) -> str:
        """
        Executa o swap na blockchain Solana.

        NOTA: Esta implementação requer a biblioteca solana-py para assinar
        e enviar transações. Por enquanto, retorna apenas a transação serializada.

        Args:
            swap_transaction: Transação serializada em base64
            wallet_private_key: Chave privada da wallet (base58)

        Returns:
            str: Transaction ID (signature)

        Raises:
            NotImplementedError: Implementação completa requer solana-py
        """
        raise NotImplementedError(
            "A execução de swaps requer a biblioteca solana-py. "
            "Use get_swap_transaction() para obter a transação serializada "
            "e execute-a usando sua própria implementação de wallet Solana."
        )

    def get_swap_instructions(
        self,
        quote_response: JupiterQuoteResponse,
        user_public_key: str,
        wrap_unwrap_sol: bool = True,
    ) -> Dict[str, Any]:
        """
        Obtém instruções de swap ao invés de uma transação completa.
        Útil para compor com outras instruções.

        Args:
            quote_response: Resposta da API de quote
            user_public_key: Chave pública do usuário (base58)
            wrap_unwrap_sol: Auto wrap/unwrap SOL (padrão: True)

        Returns:
            Dict contendo as instruções separadas
        """
        # Converte o quote_response para dict (mesmo código do get_swap_transaction)
        quote_dict = {
            "inputMint": quote_response.input_mint,
            "inAmount": quote_response.in_amount,
            "outputMint": quote_response.output_mint,
            "outAmount": quote_response.out_amount,
            "otherAmountThreshold": quote_response.other_amount_threshold,
            "swapMode": quote_response.swap_mode,
            "slippageBps": quote_response.slippage_bps,
            "platformFee": quote_response.platform_fee,
            "priceImpactPct": quote_response.price_impact_pct,
            "routePlan": [
                {
                    "swapInfo": {
                        "ammKey": rp.swap_info.amm_key,
                        "label": rp.swap_info.label,
                        "inputMint": rp.swap_info.input_mint,
                        "outputMint": rp.swap_info.output_mint,
                        "inAmount": rp.swap_info.in_amount,
                        "outAmount": rp.swap_info.out_amount,
                        "feeAmount": rp.swap_info.fee_amount,
                        "feeMint": rp.swap_info.fee_mint,
                    },
                    "percent": rp.percent,
                }
                for rp in quote_response.route_plan
            ],
        }

        data = {
            "quoteResponse": quote_dict,
            "userPublicKey": user_public_key,
            "wrapAndUnwrapSol": wrap_unwrap_sol,
        }

        return self._make_request("POST", "/swap-instructions", data=data)
