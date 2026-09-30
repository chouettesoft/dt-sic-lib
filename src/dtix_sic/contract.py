"""Load and validate DTIX-A JSON Logic contracts."""

import json
from pathlib import Path


DEFAULT_CONTRACT_PATH = Path(__file__).with_name("contracts") / "dtix_a_reference.json"

_SUPPORTED_OPERATORS = {
    "var", "if", "and", "or", "!", "!!",
    "==", "===", "!=", "!==", ">", ">=", "<", "<=",
    "in", "cat", "+", "-", "*", "/", "%", "min", "max",
    "substr", "match", "merge",
}


def load_contract(path=None):
    """Load a JSON contract from a path, or the bundled reference contract."""
    contract_path = DEFAULT_CONTRACT_PATH if path is None else Path(path)
    with contract_path.open("r", encoding="utf-8") as handle:
        contract = json.load(handle)
    validate_contract(contract)
    return contract


def validate_contract(contract):
    """Validate contract structure and every JSON Logic expression."""
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
        if "rule" not in item:
            raise ValueError(f"Rule {rule_id} is missing 'rule'.")
        validate_expression(item["rule"], f"rule '{rule_id}'")

    return True


def validate_expression(expression, location="expression"):
    """Validate a JSON Logic AST without evaluating it."""
    if expression is None or isinstance(expression, (str, int, float, bool)):
        return
    if isinstance(expression, list):
        for index, item in enumerate(expression):
            validate_expression(item, f"{location}[{index}]")
        return
    if not isinstance(expression, dict) or len(expression) != 1:
        raise ValueError(f"{location} must be a JSON Logic expression with exactly one operator.")

    operator, raw_args = next(iter(expression.items()))
    if operator not in _SUPPORTED_OPERATORS:
        raise ValueError(f"{location} uses unsupported JSON Logic operator: {operator}")
    args = raw_args if isinstance(raw_args, list) else [raw_args]

    arity = {
        "var": (1, 2), "!": (1, 1), "!!": (1, 1),
        "==": (2, 2), "===": (2, 2), "!=": (2, 2), "!==": (2, 2),
        ">": (2, 2), ">=": (2, 2), "<": (2, 2), "<=": (2, 2),
        "in": (2, 2), "-": (1, None), "/": (2, 2), "%": (2, 2),
        "substr": (2, 3), "match": (2, 2),
    }.get(operator)
    if arity:
        minimum, maximum = arity
        if len(args) < minimum or (maximum is not None and len(args) > maximum):
            suffix = str(minimum) if maximum == minimum else f"{minimum} or {maximum}"
            raise ValueError(f"{location}: {operator} requires {suffix} argument(s).")

    if operator == "if" and len(args) < 2:
        raise ValueError(f"{location}: if requires at least two arguments.")
    if operator in ("min", "max") and not args:
        raise ValueError(f"{location}: {operator} requires at least one argument.")

    for index, arg in enumerate(args):
        validate_expression(arg, f"{location}.{operator}[{index}]")
