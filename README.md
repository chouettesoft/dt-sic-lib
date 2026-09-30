# DTIX-A SIC Python Library

Functional, non-OOP Python library for DTIX-A Semantic Information Contract
validation and benchmarking.

## Design

There are **no user-defined classes and no dataclasses** in the package.
The API uses functions, dictionaries, tuples, and RDFLib's external `Graph`
representation.

## Installation

On PEP 668 protected Linux systems:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Basic use

```python
from dtix_sic import build_payload, parse_jsonld, validate_sic

payload = build_payload(10_000)
graph = parse_jsonld(payload)

if validate_sic(graph):
    print("SIC valid")
```

## Detailed validation

```python
result = validate_sic(graph, collect_errors=True)

print(result["valid"])
print(result["errors"])
```

## Tests

```bash
pytest
```

The test suite prints per-test wall-clock timings and a total measured test
runtime in the pytest terminal summary. The timing is intended for regression
visibility, not as a substitute for the dedicated benchmark module.

## v0.4.0: deterministic policy engine

The library now separates **contract validation** from **policy decisions**.
Contracts answer whether a payload satisfies its SIC rules; policies answer
what may be done with that payload in a supplied request/context.

Policies are JSON documents with:

- `id` and `version` for provenance;
- `rules[]` containing JSON Logic `when` expressions;
- `ALLOW` or `DENY` effects;
- `deny-overrides` or `first-applicable` combining;
- optional typed obligations such as audit requirements.

The canonical policy context is: `payload`, `contract`, `subject`, `resource`,
`request`, and `environment`. Evaluation is deterministic and returns a
provenance-rich decision:

```python
from dtix_sic import evaluate_policy, load_policy

policy = load_policy()
result = evaluate_policy(policy, {
    "payload": {"classification": "normal"},
    "contract": {"valid": True, "errors": ()},
    "subject": {"roles": ["researcher"]},
    "resource": {},
    "request": {"action": "share", "purpose": "research"},
    "environment": {},
})

assert result["decision"] in {
    "ALLOW", "DENY", "NOT_APPLICABLE", "INDETERMINATE"
}
```

For the integrated flow, `authorize_sic()` validates the RDF payload with the
selected contract, builds the canonical policy context, and evaluates the
policy in one call. The bundled reference policy is
`contracts/dtix_a_sharing_reference.json`.

## v0.3.1: validation hardening and test timings

The validator now rejects ambiguous graphs containing multiple `dtix:Payload` subjects. Contract validation also rejects duplicate rule IDs, unknown JSON Logic operators, and invalid operator arity before evaluation.

## v0.3.0: JSON Logic contracts

The validator no longer contains the seven DTIX-A rules in Python. They are stored in:

`src/dtix_sic/contracts/dtix_a_reference.json`

The contract uses JSON Logic expressions, for example:

```json
{
  "id": "confidence_minimum",
  "message": "confidence must be at least 0.80.",
  "rule": {
    ">=": [
      {"var": "confidence"},
      0.8
    ]
  }
}
```

Use the bundled contract automatically:

```python
from dtix_sic import parse_jsonld, validate_sic

graph = parse_jsonld(payload)
assert validate_sic(graph)
```

Or load a different JSON contract:

```python
from dtix_sic import load_contract, validate_sic

contract = load_contract("contracts/my_contract.json")
result = validate_sic(graph, contract, collect_errors=True)
```

No Python `eval()` is used. The library contains a small deterministic JSON Logic evaluator and currently supports `var`, `if`, `and`, `or`, `!`, `!!`, comparisons, `in`, `cat`, arithmetic, `min`, `max`, `substr`, `match`, and `merge`.
