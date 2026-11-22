import math
from src.observability.metrics import LLM_ESTIMATED_TOKENS


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4)) if text else 0


def record_llm_usage(
    stage: str,
    input_text: str,
    output_text: str,
) -> None:
    LLM_ESTIMATED_TOKENS.labels(stage=stage, direction="input").inc(
        estimate_tokens(input_text)
    )
    LLM_ESTIMATED_TOKENS.labels(stage=stage, direction="output").inc(
        estimate_tokens(output_text)
    )
