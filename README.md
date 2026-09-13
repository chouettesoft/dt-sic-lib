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
