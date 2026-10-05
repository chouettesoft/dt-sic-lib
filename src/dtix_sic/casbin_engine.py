"""Casbin engine adapter used by the SIC policy API."""

from pathlib import Path


def _require_casbin():
    try:
        import casbin
    except ImportError as exc:
        raise RuntimeError(
            "Casbin is required for policy authorization. Install the 'pycasbin' dependency."
        ) from exc
    return casbin


def _has_role(subject, role):
    if role == "*":
        return True
    if isinstance(subject, dict):
        roles = subject.get("roles", [])
        if isinstance(roles, str):
            roles = [roles]
        return role in roles or subject.get("role") == role or subject.get("id") == role
    if isinstance(subject, str):
        return subject == role
    return False


def _resource_matches(resource, policy_object):
    if policy_object == "*":
        return True
    if isinstance(resource, dict):
        return policy_object in {
            str(resource.get("type", "")),
            str(resource.get("classification", "")),
            str(resource.get("id", "")),
        }
    return str(resource) == policy_object


def build_enforcer(model_path, policy_path):
    """Create a Casbin enforcer and register SIC attribute matchers."""
    casbin = _require_casbin()
    enforcer = casbin.Enforcer(str(model_path), str(policy_path))
    enforcer.add_function("has_role", _has_role)
    enforcer.add_function("resource_matches", _resource_matches)
    return enforcer


def authorize_with_casbin(context, *, model_path, policy_path):
    """Evaluate a canonical SIC context with Casbin and return a stable decision."""
    model_path = Path(model_path)
    policy_path = Path(policy_path)
    if not model_path.is_file():
        raise ValueError(f"Casbin model file does not exist: {model_path}")
    if not policy_path.is_file():
        raise ValueError(f"Casbin policy file does not exist: {policy_path}")

    enforcer = build_enforcer(model_path, policy_path)
    subject = context.get("subject", {})
    resource = context.get("resource", {})
    request = context.get("request", {})
    action = request.get("action", "") if isinstance(request, dict) else ""

    allowed, matched = enforcer.enforce_ex(subject, resource, action)
    decision = "ALLOW" if allowed else "DENY"
    return {
        "decision": decision,
        "matched_rules": matched,
        "casbin": {
            "model": str(model_path),
            "policy": str(policy_path),
        },
        "context": context,
    }
