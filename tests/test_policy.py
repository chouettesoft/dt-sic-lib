from unittest.mock import patch

import pytest

from dtix_sic import (
    authorize_sic,
    authorize_with_casbin,
    build_policy_context,
    load_policy,
    parse_jsonld,
    build_payload,
    validate_policy,
)


def test_reference_casbin_policy_loads():
    policy = load_policy()
    assert "p, 10, researcher, telemetry, share, allow" in policy
    assert "p, 1, researcher, restricted, share, deny" in policy


def test_policy_configuration_validation():
    assert validate_policy({"model_path": "model.conf", "policy_path": "policy.csv"})
    with pytest.raises(ValueError, match="model_path"):
        validate_policy({"model_path": ""})
    with pytest.raises(ValueError, match="JSON object"):
        validate_policy("policy")


def test_build_policy_context_has_stable_sections():
    context = build_policy_context(
        {"confidence": 0.9}, {"valid": True, "errors": ()},
        subject={"roles": ["researcher"]}, request={"action": "share"},
    )
    assert context["payload"]["confidence"] == 0.9
    assert context["contract"]["valid"] is True
    assert context["subject"]["roles"] == ["researcher"]
    assert context["resource"] == {}
    assert context["request"]["action"] == "share"
    assert context["environment"] == {}


def test_authorize_with_casbin_normalizes_boolean_result(tmp_path):
    model = tmp_path / "model.conf"; policy = tmp_path / "policy.csv"
    model.write_text("model"); policy.write_text("policy")
    with patch("dtix_sic.casbin_engine.build_enforcer") as build:
        build.return_value.enforce_ex.return_value = (True, ["p, 10, researcher, telemetry, share, allow"])
        result = authorize_with_casbin({"subject": {"roles": ["researcher"]}, "request": {"action": "share"}}, model_path=model, policy_path=policy)
    assert result["decision"] == "ALLOW"
    assert result["matched_rules"]


def test_authorize_with_casbin_denies_when_enforcer_denies(tmp_path):
    model = tmp_path / "model.conf"; policy = tmp_path / "policy.csv"
    model.write_text("model"); policy.write_text("policy")
    with patch("dtix_sic.casbin_engine.build_enforcer") as build:
        build.return_value.enforce_ex.return_value = (False, [])
        result = authorize_with_casbin({"subject": {}, "request": {"action": "share"}}, model_path=model, policy_path=policy)
    assert result["decision"] == "DENY"


def test_authorize_sic_sends_contract_and_request_context_to_casbin():
    graph = parse_jsonld(build_payload(5000))
    captured = {}

    def fake_authorize(context, **kwargs):
        captured["context"] = context
        captured["kwargs"] = kwargs
        return {"decision": "ALLOW", "matched_rules": []}

    with patch("dtix_sic.policy.authorize_with_casbin", side_effect=fake_authorize), \
         patch("dtix_sic.validator.validate_sic", return_value={"valid": True, "errors": ()}):
        result = authorize_sic(
            graph,
            contract={"rules": []},
            request={"action": "share"},
            subject={"roles": ["researcher"]},
        )

    assert result["decision"] == "ALLOW"
    assert captured["context"]["contract"]["valid"] is True
    assert captured["context"]["request"]["action"] == "share"
    assert captured["kwargs"]["model_path"].name == "dtix_a_model.conf"
    assert captured["kwargs"]["policy_path"].name == "dtix_a_policy.csv"
