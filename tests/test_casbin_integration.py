from pathlib import Path

import pytest

casbin = pytest.importorskip("casbin")

from dtix_sic import authorize_with_casbin


ROOT = Path(__file__).parents[1]
MODEL = ROOT / "src" / "dtix_sic" / "policies" / "dtix_a_model.conf"
POLICY = ROOT / "src" / "dtix_sic" / "policies" / "dtix_a_policy.csv"


def test_reference_casbin_allow():
    result = authorize_with_casbin(
        {"subject": {"roles": ["researcher"]}, "resource": {"type": "telemetry"}, "request": {"action": "share"}},
        model_path=MODEL,
        policy_path=POLICY,
    )
    assert result["decision"] == "ALLOW"


def test_reference_casbin_deny_restricted():
    result = authorize_with_casbin(
        {"subject": {"roles": ["researcher"]}, "resource": {"type": "telemetry", "classification": "restricted"}, "request": {"action": "share"}},
        model_path=MODEL,
        policy_path=POLICY,
    )
    assert result["decision"] == "DENY"


def test_reference_casbin_denies_unmatched_action():
    result = authorize_with_casbin(
        {"subject": {"roles": ["researcher"]}, "resource": {"type": "telemetry"}, "request": {"action": "delete"}},
        model_path=MODEL,
        policy_path=POLICY,
    )
    assert result["decision"] == "DENY"
