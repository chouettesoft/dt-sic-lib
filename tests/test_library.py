import pytest
from rdflib import Graph, RDF, URIRef

from dtix_sic import (
    build_payload,
    load_contract,
    parse_jsonld,
    validate_sic,
    graph_to_data,
    evaluate_cel,
    get_payload_subject,
    validate_contract,
)
from dtix_sic.context import EX


def test_valid_payload():
    pytest.importorskip("celpy")
    graph = parse_jsonld(build_payload(5000))
    assert validate_sic(graph)


def test_contract_uses_cel_expressions():
    pytest.importorskip("celpy")
    contract = load_contract()
    assert contract["contract"] == "DTIX-A-SIC"
    assert len(contract["rules"]) == 7
    assert all(isinstance(rule["expression"], str) for rule in contract["rules"])


def test_extra_rules_can_be_added_to_contract_dynamically():
    pytest.importorskip("celpy")
    graph = parse_jsonld(build_payload(5000, extra_rules=20))
    contract = load_contract()
    contract["rules"].extend(
        {
            "id": f"rule_{index}",
            "message": f"rule_{index} must equal {index}.",
            "expression": f"rule_{index} == {index}",
        }
        for index in range(20)
    )
    assert validate_sic(graph, contract)


def test_invalid_payload():
    pytest.importorskip("celpy")
    payload = build_payload(5000).replace('"confidence":0.87', '"confidence":0.50')
    graph = parse_jsonld(payload)
    assert not validate_sic(graph)


def test_error_details():
    pytest.importorskip("celpy")
    payload = build_payload(5000).replace('"latency_ms":12.4', '"latency_ms":100')
    graph = parse_jsonld(payload)
    result = validate_sic(graph, collect_errors=True)
    assert result["valid"] is False
    assert any("latency_ms" in error for error in result["errors"])


def test_cel_expression():
    pytest.importorskip("celpy")
    assert bool(evaluate_cel("confidence >= 0.80", {"confidence": 0.87}))
    assert bool(evaluate_cel("rul_hours > 0 && latency_ms <= 50", {"rul_hours": 12.5, "latency_ms": 12.4}))


def test_graph_to_data():
    graph = parse_jsonld(build_payload(5000))
    subject = get_payload_subject(graph)
    data = graph_to_data(graph, subject)
    assert data["asset_id"] == "ARM-ROBOT-892"
    assert data["confidence"] == 0.87


def test_contract_rejects_duplicate_rule_ids():
    contract = {"rules": [{"id": "x", "expression": "true"}]}
    contract["rules"].append(dict(contract["rules"][0]))
    with pytest.raises(ValueError, match="Duplicate rule id"):
        validate_contract(contract)


def test_contract_rejects_missing_expression():
    contract = {"rules": [{"id": "x"}]}
    with pytest.raises(ValueError, match="non-empty string 'expression'"):
        validate_contract(contract)


def test_multiple_payload_subjects_are_not_silently_selected():
    pytest.importorskip("celpy")
    graph = parse_jsonld(build_payload(5000))
    graph.add((URIRef("https://example.org/dtix#payload-2"), RDF.type, EX.Payload))
    with pytest.raises(ValueError, match="multiple dtix:Payload"):
        get_payload_subject(graph)
    assert validate_sic(graph, collect_errors=True)["valid"] is False


def test_dependency_policy_is_python39_compatible():
    from pathlib import Path
    pyproject = Path(__file__).parents[1] / "pyproject.toml"
    text = pyproject.read_text()
    assert '"cel-python==0.4.0"' in text
    assert '"google-re2==1.1.20240702"' in text
