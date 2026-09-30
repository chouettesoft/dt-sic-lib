import pytest

from dtix_sic import (
    build_policy_context,
    evaluate_policy,
    load_policy,
    validate_policy,
)


def _policy(**overrides):
    policy = {
        "id": "test-policy",
        "version": "1.0.0",
        "combining": "deny-overrides",
        "rules": [
            {
                "id": "deny-restricted",
                "when": {"==": [{"var": "payload.classification"}, "restricted"]},
                "effect": "DENY",
                "obligations": [{"type": "audit", "event": "denied"}],
            },
            {
                "id": "allow-valid",
                "when": {"==": [{"var": "contract.valid"}, True]},
                "effect": "ALLOW",
                "obligations": [{"type": "audit", "event": "allowed"}],
            },
        ],
    }
    policy.update(overrides)
    return policy


def test_reference_policy_loads():
    policy = load_policy()
    assert policy["id"] == "dtix-a-sharing-reference"
    assert validate_policy(policy)


def test_deny_overrides_allow_and_preserves_provenance():
    result = evaluate_policy(
        _policy(),
        {"payload": {"classification": "restricted"}, "contract": {"valid": True}},
    )
    assert result["decision"] == "DENY"
    assert result["matched_rules"] == ("deny-restricted", "allow-valid")
    assert result["obligations"][0]["type"] == "audit"
    assert result["obligations"][0]["event"] == "denied"
    assert all(item.get("event") != "allowed" for item in result["obligations"])
    assert result["policy"] == "test-policy"
    assert result["policy_version"] == "1.0.0"


def test_first_applicable_stops_at_first_match():
    policy = _policy(combining="first-applicable")
    result = evaluate_policy(policy, {"payload": {"classification": "restricted"}, "contract": {"valid": True}})
    assert result["decision"] == "DENY"
    assert result["matched_rules"] == ("deny-restricted",)


def test_not_applicable_when_no_rule_matches():
    result = evaluate_policy(_policy(), {"payload": {}, "contract": {"valid": False}})
    assert result["decision"] == "NOT_APPLICABLE"
    assert result["matched_rules"] == ()


def test_invalid_policy_is_rejected_before_evaluation():
    policy = _policy(rules=[{"id": "bad", "when": {"eval": [1]}, "effect": "ALLOW"}])
    with pytest.raises(ValueError, match="unsupported JSON Logic operator"):
        evaluate_policy(policy, {})


def test_duplicate_policy_rule_ids_are_rejected():
    policy = _policy()
    policy["rules"].append(dict(policy["rules"][0]))
    with pytest.raises(ValueError, match="Duplicate policy rule id"):
        validate_policy(policy)


def test_unknown_effect_is_rejected():
    policy = _policy(rules=[{"id": "x", "when": True, "effect": "REQUIRE_CONSENT"}])
    with pytest.raises(ValueError, match="unsupported effect"):
        validate_policy(policy)


def test_policy_context_has_stable_sections():
    context = build_policy_context(
        {"confidence": 0.9}, {"valid": True, "errors": ()},
        subject={"roles": ["researcher"]},
        request={"action": "share"},
    )
    assert context["payload"]["confidence"] == 0.9
    assert context["contract"]["valid"] is True
    assert context["subject"]["roles"] == ["researcher"]
    assert context["resource"] == {}
    assert context["request"]["action"] == "share"
    assert context["environment"] == {}


def test_authorize_sic_composes_contract_and_policy():
    from dtix_sic import authorize_sic, build_payload, parse_jsonld

    graph = parse_jsonld(build_payload(5000))
    policy = {
        "id": "authorization-test",
        "version": "1.0.0",
        "combining": "deny-overrides",
        "rules": [
            {
                "id": "allow-sharing",
                "when": {
                    "and": [
                        {"==": [{"var": "contract.valid"}, True]},
                        {"==": [{"var": "request.action"}, "share"]},
                    ]
                },
                "effect": "ALLOW",
            }
        ],
    }
    result = authorize_sic(graph, policy, request={"action": "share"})
    assert result["decision"] == "ALLOW"
    assert result["matched_rules"] == ("allow-sharing",)
