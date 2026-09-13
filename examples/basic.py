from dtix_sic import build_payload, parse_jsonld, validate_sic

payload = build_payload(10_000)
graph = parse_jsonld(payload)
result = validate_sic(graph, collect_errors=True)

if result["valid"]:
    print("SIC validation passed")
else:
    print("SIC validation failed:")
    for error in result["errors"]:
        print(f" - {error}")
