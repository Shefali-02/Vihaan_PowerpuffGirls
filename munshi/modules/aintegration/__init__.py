import os

from .llm_gateway import (MOCK_BADGE, InMemoryRunStore, LlmGateway, LlmRequest, LlmResponse,
                          LlmValidationError)
from .prune_client import PruneClient
from .prune_mock import PruneMock

__all__ = ["LlmGateway", "LlmRequest", "LlmResponse", "LlmValidationError", "PruneClient",
           "PruneMock", "InMemoryRunStore", "MOCK_BADGE", "build_gateway"]


def build_gateway(run_store=None) -> LlmGateway:
    """Real Prune only when PRUNE_BASE_URL and PRUNE_API_KEY are set and PRUNE_MODE != 'mock'.
    Otherwise the mock is used and every response carries the MOCK LLM badge."""
    use_real = (os.environ.get("PRUNE_BASE_URL") and os.environ.get("PRUNE_API_KEY")
                and os.environ.get("PRUNE_MODE", "live") != "mock")
    backend = PruneClient.from_env() if use_real else PruneMock()
    return LlmGateway(backend, run_store=run_store)
