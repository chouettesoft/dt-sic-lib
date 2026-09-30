"""Deterministic SIC policy evaluation over contract and request context."""

import json
from pathlib import Path
import re

from .contract import validate_expression
from .logic import evaluate

_SUPPORTED_EFFECTS = {"ALLOW", "DENY"}
_SUPPORTED_COMBINING = {"deny-overrides", "first-applicable"}
DEFAULT_POLICY_PATH = Path(__file__).with_name("contracts") / "dtix_a_sharing_reference.json"


def load_policy(path=None):
    """Load and validate a JSON policy from a path or the bundled reference policy."""
    policy_path = DEFAULT_POLICY_PATH if path is None else Path(path)
    with policy_path.open("r", encoding="utf-8") as handle:
        policy = json.load(handle)
    validate_policy(policy)
    return policy


def validate_policy(policy):
    """Validate a policy structure without executing its rules."""
    if not isinstance(policy, dict):
        raise ValueError("Policy must be a JSON object.")

    policy_id = policy.get("id")
    if not isinstance(policy_id, str) or not policy_id:
        raise ValueError("Policy must have a non-empty string 'id'.")

    version = policy.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("Policy must have a non-empty string 'version'.")

    combining = policy.get("combining", "deny-overrides")
    if combining not in _SUPPORTED_COMBINING:
        raise ValueError(f"Unsupported policy combining algorithm: {combining}")

    rules = policy.get("rules")
    if not isinstance(rules, list):
        raise ValueError("Policy 'rules' must be a JSON array.")

    rule_ids = set()
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise ValueError(f"Policy rule {index} must be a JSON object.")
        rule_id = rule.get("id")
        if not isinstance(rule_id, str) or not rule_id:
            raise ValueError(f"Policy rule {index} must have a non-empty string 'id'.")
        if rule_id in rule_ids:
            raise ValueError(f"Duplicate policy rule id: {rule_id}.")
        rule_ids.add(rule_id)

        if "when" not in rule:
            raise ValueError(f"Policy rule {rule_id} is missing 'when'.")
        validate_expression(rule["when"], f"policy rule '{rule_id}'")

        effect = rule.get("effect")
        if effect not in _SUPPORTED_EFFECTS:
            raise ValueError(
                f"Policy rule {rule_id} has unsupported effect: {effect}."
            )

        obligations = rule.get("obligations", [])
        _validate_obligations(obligations, rule_id)

    return True


def evaluate_policy(policy, context):
    """Evaluate a validated policy and return a deterministic decision dictionary.

    Decisions are ``ALLOW``, ``DENY``, ``NOT_APPLICABLE``, or ``INDETERMINATE``.
    ``deny-overrides`` evaluates every rule and gives any matching DENY precedence.
    ``first-applicable`` stops at the first matching rule.
    """
    validate_policy(policy)

    combining = policy.get("combining", "deny-overrides")
    matched = []

    for rule in policy["rules"]:
        try:
            applies = bool(evaluate(rule["when"], context))
        except (TypeError, ValueError, ZeroDivisionError, OverflowError, re.error) as exc:
            return {
                "decision": "INDETERMINATE",
                "policy": policy["id"],
                "policy_version": policy["version"],
                "matched_rules": tuple(item["id"] for item in matched),
                "obligations": tuple(
                    obligation
                    for item in matched
                    for obligation in item.get("obligations", [])
                ),
                "errors": (f"{rule['id']}: evaluation error: {exc}",),
            }

        if not applies:
            continue

        matched.append(rule)

        if combining == "first-applicable":
            return _decision(policy, rule["effect"], matched)

    if not matched:
        return _decision(policy, "NOT_APPLICABLE", matched)

    effective_effect = "DENY" if any(rule["effect"] == "DENY" for rule in matched) else "ALLOW"
    return _decision(policy, effective_effect, matched)


def authorize_sic(graph, policy=None, contract=None, *, subject=None, resource=None,
                  request=None, environment=None):
    """Validate an RDF payload and evaluate a policy against its canonical context."""
    from .contract import load_contract
    from .validator import graph_to_data, get_payload_subject, validate_sic

    selected_contract = load_contract(contract) if contract is None or isinstance(contract, (str, bytes)) else contract
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
    selected_policy = load_policy() if policy is None or isinstance(policy, (str, bytes)) else policy
    return evaluate_policy(selected_policy, context)


def build_policy_context(payload, contract_result, *, subject=None, resource=None,
                         request=None, environment=None):
    """Build the canonical context supplied to policy expressions."""
    return {
        "payload": payload,
        "contract": contract_result,
        "subject": subject or {},
        "resource": resource or {},
        "request": request or {},
        "environment": environment or {},
    }


def _decision(policy, decision, matched):
    effective = [rule for rule in matched if rule["effect"] == decision]
    obligations = [
        obligation
        for rule in effective
        for obligation in rule.get("obligations", [])
    ]
    return {
        "decision": decision,
        "policy": policy["id"],
        "policy_version": policy["version"],
        "matched_rules": tuple(rule["id"] for rule in matched),
        "obligations": tuple(obligations),
        "errors": (),
    }


def _validate_obligations(obligations, rule_id):
    if not isinstance(obligations, list):
        raise ValueError(f"Policy rule {rule_id} 'obligations' must be a JSON array.")
    for index, obligation in enumerate(obligations):
        if not isinstance(obligation, dict):
            raise ValueError(
                f"Policy rule {rule_id} obligation {index} must be a JSON object."
            )
        obligation_type = obligation.get("type")
        if not isinstance(obligation_type, str) or not obligation_type:
            raise ValueError(
                f"Policy rule {rule_id} obligation {index} needs a non-empty string 'type'."
            )


