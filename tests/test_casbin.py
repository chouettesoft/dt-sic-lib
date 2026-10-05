from pathlib import Path
from unittest.mock import patch

import pytest

from dtix_sic.casbin_engine import _has_role, _resource_matches, authorize_with_casbin


def test_has_role_supports_role_lists():
    assert _has_role({"roles": ["researcher"]}, "researcher")
    assert not _has_role({"roles": ["operator"]}, "researcher")
    assert _has_role({}, "*")


def test_resource_matches_type_and_classification():
    resource = {"type": "telemetry", "classification": "restricted"}
    assert _resource_matches(resource, "telemetry")
    assert _resource_matches(resource, "restricted")
    assert not _resource_matches(resource, "public")


def test_authorize_requires_model_and_policy_files(tmp_path):
    with pytest.raises(ValueError, match="model file"):
        authorize_with_casbin({}, model_path=tmp_path / "missing.conf", policy_path=tmp_path / "policy.csv")
