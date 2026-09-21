"""DTIX-A Semantic Information Contract validation library."""

from .context import EX, build_context
from .payload import build_payload
from .rdf import parse_jsonld
from .contract import load_contract, validate_contract
from .logic import evaluate
from .validator import validate_sic, get_payload_subject, get_first_value, graph_to_data
from .benchmark import run_payload_experiment, run_contract_complexity_experiment, summarize_samples

__all__ = [
    "EX", "build_context", "build_payload", "parse_jsonld",
    "load_contract", "validate_contract", "evaluate",
    "validate_sic", "get_payload_subject", "get_first_value", "graph_to_data",
    "run_payload_experiment", "run_contract_complexity_experiment",
    "summarize_samples",
]
