"""Functional DTIX-A Semantic Information Contract validation."""

from rdflib import RDF

from .context import EX


def get_payload_subject(graph):
    """Return the first subject typed as dtix:Payload, or None."""
    return next(graph.subjects(RDF.type, EX.Payload), None)


def get_first_value(graph, subject, predicate):
    """Return the first RDF value for a predicate, or None."""
    return next(graph.objects(subject, predicate), None)


def validate_sic(graph, extra_rules=0, collect_errors=False):
    """
    Validate the DTIX-A reference SIC.

    Returns bool by default.

    With collect_errors=True, returns:
        {"valid": bool, "errors": tuple[str, ...]}

    No user-defined classes or dataclasses are used.
    """
    if extra_rules < 0:
        raise ValueError("extra_rules must be >= 0")

    errors = []
    subject = get_payload_subject(graph)

    if subject is None:
        errors.append("No dtix:Payload subject exists.")
        return _result(False, errors, collect_errors)

    checks = (
        ("asset_id must exist.", bool(get_first_value(graph, subject, EX.asset_id))),
        ('information_type must be "computed".',
         _string_equals(graph, subject, EX.information_type, "computed")),
        ("rul_hours must be greater than zero.",
         _numeric_check(graph, subject, EX.rul_hours, lambda value: value > 0)),
        ("confidence must be at least 0.80.",
         _numeric_check(graph, subject, EX.confidence, lambda value: value >= 0.80)),
        ("model_id must exist.", bool(get_first_value(graph, subject, EX.model_id))),
        ("model_version must exist.",
         bool(get_first_value(graph, subject, EX.model_version))),
        ("latency_ms must not exceed 50.",
         _numeric_check(graph, subject, EX.latency_ms, lambda value: value <= 50)),
    )

    for message, passed in checks:
        if not passed:
            errors.append(message)

    for index in range(extra_rules):
        predicate = EX[f"rule_{index}"]
        value = get_first_value(graph, subject, predicate)

        if value is None:
            errors.append(f"rule_{index} is missing.")
            continue

        try:
            valid = int(value) == index
        except (TypeError, ValueError):
            valid = False

        if not valid:
            errors.append(f"rule_{index} must equal {index}.")

    return _result(not errors, errors, collect_errors)


def _result(valid, errors, collect_errors):
    if not collect_errors:
        return valid
    return {"valid": valid, "errors": tuple(errors)}


def _string_equals(graph, subject, predicate, expected):
    value = get_first_value(graph, subject, predicate)
    return value is not None and str(value) == expected


def _numeric_check(graph, subject, predicate, condition):
    value = get_first_value(graph, subject, predicate)
    if value is None:
        return False
    try:
        return bool(condition(float(value)))
    except (TypeError, ValueError):
        return False
