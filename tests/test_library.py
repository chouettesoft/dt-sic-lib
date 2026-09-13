from dtix_sic import build_payload, parse_jsonld, validate_sic


def test_valid_payload():
    graph = parse_jsonld(build_payload(5000))
    assert validate_sic(graph)


def test_extra_rules():
    graph = parse_jsonld(build_payload(5000, extra_rules=20))
    assert validate_sic(graph, extra_rules=20)


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
