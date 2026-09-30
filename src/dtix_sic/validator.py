"""Functional DTIX-A Semantic Information Contract validation using JSON Logic."""

from rdflib import Literal, RDF

from .context import EX
from .contract import load_contract, validate_contract
from .logic import evaluate


def get_payload_subject(graph):
    """Return the unique dtix:Payload subject, or None when there is none."""
    subjects = list(graph.subjects(RDF.type, EX.Payload))
    if len(subjects) > 1:
        raise ValueError("Graph contains multiple dtix:Payload subjects.")
    return subjects[0] if subjects else None


def get_first_value(graph, subject, predicate):
    """Return the first RDF value for a predicate, or None."""
    return next(graph.objects(subject, predicate), None)


def graph_to_data(graph, subject):
    """Convert the selected RDF subject into JSON-compatible rule input."""
    data = {}
    for predicate, value in graph.predicate_objects(subject):
        key = _predicate_name(predicate)
        if key == "type" or not isinstance(value, Literal):
            continue
        converted = _rdf_value_to_python(value)
        if key not in data:
            data[key] = converted
        elif isinstance(data[key], list):
            data[key].append(converted)
        else:
            data[key] = [data[key], converted]
    return data


def validate_sic(graph, contract=None, collect_errors=False):
    """Evaluate all JSON Logic rules from a contract against an RDF payload.

    ``contract`` may be a loaded contract dictionary or a path to a JSON file.
    When omitted, the project's bundled DTIX-A reference contract is used.

    Returns bool by default. With ``collect_errors=True`` it returns a plain
    dictionary containing ``valid`` and a tuple of rule error messages.
    Structural contract errors and ambiguous payload graphs raise ``ValueError``.
    """
    if contract is None or isinstance(contract, (str, bytes)):
        contract = load_contract(contract)
    else:
        validate_contract(contract)

    try:
        subject = get_payload_subject(graph)
    except ValueError as exc:
        errors = (str(exc),)
        return {"valid": False, "errors": errors} if collect_errors else False

    if subject is None:
        errors = ("No dtix:Payload subject exists.",)
        return {"valid": False, "errors": errors} if collect_errors else False

    data = graph_to_data(graph, subject)
    errors = []

    for rule in contract["rules"]:
        try:
            passed = bool(evaluate(rule["rule"], data))
        except (TypeError, ValueError, ZeroDivisionError, OverflowError) as exc:
            passed = False
            errors.append(f"{rule['id']}: evaluation error: {exc}")
            continue

        if not passed:
            errors.append(rule.get("message", f"Rule '{rule['id']}' failed."))

    valid = not errors
    if not collect_errors:
        return valid
    return {"valid": valid, "errors": tuple(errors)}


def _predicate_name(predicate):
    value = str(predicate)
    if value.startswith(str(EX)):
        return value[len(str(EX)):]
    return value.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _rdf_value_to_python(value):
    if value is None:
        return None
    try:
        if value.datatype:
            datatype = str(value.datatype)
            if datatype.endswith("#integer") or datatype.endswith("#int"):
                return int(value)
            if datatype.endswith("#decimal") or datatype.endswith("#double") or datatype.endswith("#float"):
                return float(value)
            if datatype.endswith("#boolean"):
                return str(value).lower() == "true"
    except (TypeError, ValueError):
        pass
    return str(value)
