"""Load DTIX-A JSON Logic contracts."""

import json
from pathlib import Path


DEFAULT_CONTRACT_PATH = Path(__file__).with_name("contracts") / "dtix_a_reference.json"


def load_contract(path=None):
    """Load a JSON contract from a path, or the bundled reference contract."""
    contract_path = DEFAULT_CONTRACT_PATH if path is None else Path(path)
    with contract_path.open("r", encoding="utf-8") as handle:
        contract = json.load(handle)
    validate_contract(contract)
    return contract


def validate_contract(contract):
    """Perform minimal structural validation of a JSON Logic contract."""
    if not isinstance(contract, dict):
        raise ValueError("Contract must be a JSON object.")
    rules = contract.get("rules")
    if not isinstance(rules, list):
        raise ValueError("Contract 'rules' must be a JSON array.")

    for index, item in enumerate(rules):
        if not isinstance(item, dict):
            raise ValueError(f"Rule {index} must be a JSON object.")
        if not isinstance(item.get("id"), str) or not item["id"]:
            raise ValueError(f"Rule {index} must have a non-empty string 'id'.")
        if "rule" not in item:
            raise ValueError(f"Rule {item['id']} is missing 'rule'.")

    return True
