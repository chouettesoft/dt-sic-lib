"""DTIX-A Semantic Information Contract validation with CEL and Casbin."""

from .context import EX, build_context
from .payload import build_payload
from .rdf import parse_jsonld
from .contract import load_contract, validate_contract, validate_expression
from .cel import evaluate_cel, validate_cel_expression, clear_cel_cache
from .casbin_engine import authorize_with_casbin, build_enforcer
from .policy import load_policy, validate_policy, build_policy_context, authorize_sic
from .validator import validate_sic, get_payload_subject, get_first_value, graph_to_data
from .benchmark import run_payload_experiment, run_contract_complexity_experiment, summarize_samples

__all__ = [
    "EX", "build_context", "build_payload", "parse_jsonld",
    "load_contract", "validate_contract", "validate_expression",
    "evaluate_cel", "validate_cel_expression", "clear_cel_cache",
    "authorize_with_casbin", "build_enforcer",
    "load_policy", "validate_policy", "build_policy_context", "authorize_sic",
    "validate_sic", "get_payload_subject", "get_first_value", "graph_to_data",
    "run_payload_experiment", "run_contract_complexity_experiment", "summarize_samples",
]
