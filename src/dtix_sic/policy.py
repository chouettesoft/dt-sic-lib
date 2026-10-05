"""Casbin-backed policy decisions for SIC."""

from pathlib import Path

from .contract import load_contract
from .casbin_engine import authorize_with_casbin, build_enforcer

POLICY_DIR = Path(__file__).with_name("policies")
DEFAULT_MODEL_PATH = POLICY_DIR / "dtix_a_model.conf"
DEFAULT_POLICY_PATH = POLICY_DIR / "dtix_a_policy.csv"


def load_policy(path=None):
    """Load the bundled or user-supplied Casbin policy CSV as text."""
    policy_path = DEFAULT_POLICY_PATH if path is None else Path(path)
    return policy_path.read_text(encoding="utf-8")


def validate_policy(policy):
    """Validate Casbin policy configuration."""
    if policy is None:
        return True
    if not isinstance(policy, dict):
        raise ValueError("Policy configuration must be a JSON object.")
    for key in ("model_path", "policy_path"):
        if key in policy and (not isinstance(policy[key], (str, Path)) or not str(policy[key]).strip()):
            raise ValueError(f"Policy configuration needs a non-empty '{key}'.")
    return True


def build_policy_context(payload, contract_result, *, subject=None, resource=None,
                         request=None, environment=None):
    """Build the canonical context used by the Casbin adapter."""
    return {
        "payload": payload,
        "contract": contract_result,
        "subject": subject or {},
        "resource": resource or {},
        "request": request or {},
        "environment": environment or {},
    }


def authorize_sic(graph, policy=None, contract=None, *, subject=None, resource=None,
                  request=None, environment=None, model_path=None, policy_path=None):
    """Validate an RDF payload and authorize it with a local Casbin enforcer."""
    from .validator import graph_to_data, get_payload_subject, validate_sic

    selected_contract = (
        load_contract(contract)
        if contract is None or isinstance(contract, (str, bytes))
        else contract
    )
    contract_result = validate_sic(graph, selected_contract, collect_errors=True)
    try:
        payload_subject = get_payload_subject(graph)
    except ValueError as exc:
        payload_subject = None
        contract_result = dict(contract_result)
        contract_result["valid"] = False
        contract_result["errors"] = tuple(contract_result.get("errors", ())) + (str(exc),)

    payload = graph_to_data(graph, payload_subject) if payload_subject is not None else {}
    context = build_policy_context(
        payload, contract_result, subject=subject, resource=resource,
        request=request, environment=environment,
    )

    if policy is not None:
        validate_policy(policy)
        if isinstance(policy, dict):
            model_path = policy.get("model_path", model_path)
            policy_path = policy.get("policy_path", policy_path)

    return authorize_with_casbin(
        context,
        model_path=model_path or DEFAULT_MODEL_PATH,
        policy_path=policy_path or DEFAULT_POLICY_PATH,
    )
