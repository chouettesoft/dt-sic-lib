"""Load and validate DTIX-A contracts expressed with CEL."""

import json
from pathlib import Path

from .cel import validate_cel_expression

DEFAULT_CONTRACT_PATH = Path(__file__).with_name("contracts") / "dtix_a_reference.json"


def load_contract(path=None):
    """Load a JSON contract from a path, or the bundled reference contract."""
    contract_path = DEFAULT_CONTRACT_PATH if path is None else Path(path)
    with contract_path.open("r", encoding="utf-8") as handle:
        contract = json.load(handle)
    validate_contract(contract, compile_expressions=True)
    return contract


def validate_contract(contract, *, compile_expressions=False):
    """Validate contract structure and optionally compile every CEL expression."""
    if not isinstance(contract, dict):
        raise ValueError("Contract must be a JSON object.")
    rules = contract.get("rules")
    if not isinstance(rules, list):
        raise ValueError("Contract 'rules' must be a JSON array.")

    rule_ids = set()
    for index, item in enumerate(rules):
        if not isinstance(item, dict):
            raise ValueError(f"Rule {index} must be a JSON object.")
        rule_id = item.get("id")
        if not isinstance(rule_id, str) or not rule_id:
            raise ValueError(f"Rule {index} must have a non-empty string 'id'.")
        if rule_id in rule_ids:
            raise ValueError(f"Duplicate rule id: {rule_id}.")
        rule_ids.add(rule_id)
        expression = item.get("expression")
        if not isinstance(expression, str) or not expression.strip():
            raise ValueError(f"Rule {rule_id} must have a non-empty string 'expression'.")
        if compile_expressions:
            try:
                validate_cel_expression(expression)
            except Exception as exc:
                raise ValueError(f"Rule {rule_id} has invalid CEL expression: {exc}") from exc

    return True


def validate_expression(expression, location="expression"):
    """Validate the shape of a CEL expression without evaluating it."""
    if not isinstance(expression, str) or not expression.strip():
        raise ValueError(f"{location} must be a non-empty CEL expression string.")
    return True
