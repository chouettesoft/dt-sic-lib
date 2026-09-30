import pytest
from rdflib import Graph, RDF, URIRef

from dtix_sic import (
    build_payload,
    load_contract,
    parse_jsonld,
    validate_sic,
    graph_to_data,
    evaluate,
    get_payload_subject,
    validate_contract,
)
from dtix_sic.context import EX


def test_valid_payload():
    graph = parse_jsonld(build_payload(5000))
    assert validate_sic(graph)


def test_contract_is_loaded_from_json():
    contract = load_contract()
    assert contract["contract"] == "DTIX-A-SIC"
    assert len(contract["rules"]) == 7
    assert all("rule" in rule for rule in contract["rules"])


def test_extra_rules_can_be_added_to_contract_dynamically():
    graph = parse_jsonld(build_payload(5000, extra_rules=20))
    contract = load_contract()
    contract["rules"].extend(
        {
            "id": f"rule_{index}",
            "message": f"rule_{index} must equal {index}.",
            "rule": {"==": [{"var": f"rule_{index}"}, index]},
        }
        for index in range(20)
    )
    assert validate_sic(graph, contract)


def test_invalid_payload():
    payload = build_payload(5000).replace('"confidence":0.87', '"confidence":0.50')
    graph = parse_jsonld(payload)
    assert not validate_sic(graph)


def test_error_details():
    payload = build_payload(5000).replace('"latency_ms":12.4', '"latency_ms":100')
    graph = parse_jsonld(payload)
    result = validate_sic(graph, collect_errors=True)

    assert isinstance(result, dict)
    assert result["valid"] is False
    assert any("latency_ms" in error for error in result["errors"])


def test_json_logic_expression():
    assert evaluate({">=": [{"var": "confidence"}, 0.80]}, {"confidence": 0.87})
    assert evaluate({"and": [
        {">": [{"var": "rul_hours"}, 0]},
        {"<=": [{"var": "latency_ms"}, 50]},
    ]}, {"rul_hours": 12.5, "latency_ms": 12.4})


def test_graph_to_data():
    graph = parse_jsonld(build_payload(5000))
    subject = get_payload_subject(graph)
    data = graph_to_data(graph, subject)
    assert data["asset_id"] == "ARM-ROBOT-892"
    assert data["confidence"] == 0.87


def test_contract_rejects_duplicate_rule_ids():
    contract = load_contract()
    contract["rules"].append(dict(contract["rules"][0]))
    with pytest.raises(ValueError, match="Duplicate rule id"):
        validate_contract(contract)


def test_contract_rejects_unknown_json_logic_operator():
    contract = load_contract()
    contract["rules"][0]["rule"] = {"eval": [{"var": "asset_id"}]}
    with pytest.raises(ValueError, match="unsupported JSON Logic operator"):
        validate_contract(contract)


def test_contract_rejects_invalid_operator_arity():
    contract = load_contract()
    contract["rules"][0]["rule"] = {">=": [{"var": "confidence"}]}
    with pytest.raises(ValueError, match="requires 2 argument"):
        validate_contract(contract)


def test_multiple_payload_subjects_are_not_silently_selected():
    graph = parse_jsonld(build_payload(5000))
    subject = get_payload_subject(graph)
    graph.add((URIRef("https://example.org/dtix#payload-2"), RDF.type, EX.Payload))
    with pytest.raises(ValueError, match="multiple dtix:Payload"):
        get_payload_subject(graph)
    assert validate_sic(graph, collect_errors=True)["valid"] is False
