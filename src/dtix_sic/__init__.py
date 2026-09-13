"""DTIX-A Semantic Information Contract validation library."""

from .context import EX, build_context
from .payload import build_payload
from .rdf import parse_jsonld
from .validator import validate_sic, get_payload_subject, get_first_value
from .benchmark import run_payload_experiment, run_contract_complexity_experiment, summarize_samples

__all__ = [
    "EX", "build_context", "build_payload", "parse_jsonld",
    "validate_sic", "get_payload_subject", "get_first_value",
    "run_payload_experiment", "run_contract_complexity_experiment",
    "summarize_samples",
]
