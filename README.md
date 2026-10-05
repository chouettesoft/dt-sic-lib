# DTIX-A SIC Python Library

Functional DTIX-A Semantic Information Contract validation using **CEL** for
contract expressions and **Casbin** for policy decisions.

## Architecture

```text
JSON-LD -> RDFLib -> SIC contract -> CEL -> policy context -> Casbin -> decision
```

CEL and Casbin are embedded Python dependencies. CEL evaluates the contract
expressions; Casbin evaluates authorization policies using a bundled model and
policy file. This keeps the policy decision local.

Casbin's Python implementation is `pycasbin`. Casbin's model defines the
request, policy, effect, and matcher semantics, while the policy CSV contains
the concrete authorization rules. See the Casbin documentation for the model
and enforcement APIs.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

For Python 3.9, the project pins `cel-python` to 0.4.0 and the compatible
`google-re2` wheel release. Casbin 2.8.0 is pure Python and supports Python 3.9.

## Contract validation

```python
from dtix_sic import build_payload, parse_jsonld, validate_sic

graph = parse_jsonld(build_payload(10_000))
assert validate_sic(graph)
```

Contract rules use CEL strings:

```json
{
  "id": "confidence_minimum",
  "message": "confidence must be at least 0.80.",
  "expression": "confidence >= 0.8"
}
```

The bundled contract is `src/dtix_sic/contracts/dtix_a_reference.json`.

## Casbin policy engine

The default Casbin model is:

`src/dtix_sic/policies/dtix_a_model.conf`

and the bundled policy is:

`src/dtix_sic/policies/dtix_a_policy.csv`

The model uses:

- subject roles;
- resource type/classification;
- requested action;
- allow/deny effects;
- deny-overrides semantics.

For example:

```text
p, 1, researcher, restricted, share, deny
p, 10, researcher, telemetry, share, allow
```

A restricted telemetry resource therefore matches both rules, and Casbin's
policy effect denies the request.

Authorize a payload with:

```python
from dtix_sic import build_payload, parse_jsonld, authorize_sic

graph = parse_jsonld(build_payload(10_000))

decision = authorize_sic(
    graph,
    request={"action": "share", "purpose": "research"},
    subject={"roles": ["researcher"]},
    resource={"type": "telemetry", "classification": "public"},
)

print(decision["decision"])
```

The result has a stable shape:

```json
{
  "decision": "ALLOW",
  "matched_rules": [],
  "casbin": {
    "model": ".../dtix_a_model.conf",
    "policy": ".../dtix_a_policy.csv"
  },
  "context": {}
}
```

`matched_rules` contains the Casbin policy lines returned by `enforce_ex` when
Casbin exposes them. `DENY` is returned when no applicable allow exists or a
deny rule overrides an allow rule.

### Custom Casbin policies

Pass a configuration dictionary to `authorize_sic()`:

```python
result = authorize_sic(
    graph,
    policy={
        "model_path": "/etc/myapp/model.conf",
        "policy_path": "/etc/myapp/policy.csv",
    },
    subject={"roles": ["researcher"]},
    resource={"type": "telemetry"},
    request={"action": "share"},
)
```

The model and policy are intentionally separate. Casbin can therefore evolve
from the bundled CSV adapter to another supported persistence adapter without
changing the SIC contract layer.

## Policy context

The canonical context remains:

```json
{
  "payload": {},
  "contract": {},
  "subject": {},
  "resource": {},
  "request": {},
  "environment": {}
}
```

The default Casbin adapter maps this context to the Casbin request as:

```text
subject -> r.sub
resource -> r.obj
action   -> r.act
```

The built-in matcher provides two controlled functions:

- `has_role(subject, role)`
- `resource_matches(resource, policy_object)`

No arbitrary Python expression or `eval()` is used for authorization.

## Tests and timings

```bash
pytest
```

The test suite prints per-test wall-clock timings, total measured runtime, and
the slowest test. The benchmark module remains available for parsing/validation
performance experiments.

## Security boundary

Casbin is evaluated locally, so the application controls the model and policy
files. Treat custom policy/model paths as trusted configuration. Do not load
untrusted Casbin model files or policy files. CEL remains the expression engine
for contract validation and is independently validated before execution.
