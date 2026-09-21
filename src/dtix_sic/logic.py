"""Small, deterministic JSON Logic evaluator used by the SIC validator.

The implementation intentionally supports the JSON Logic operators needed by
DTIX-A and common contract expressions. It does not execute Python code or use
eval().
"""

import math
import re


_MISSING = object()


def evaluate(expression, data):
    """Evaluate one JSON Logic expression against a JSON-compatible object."""
    if expression is None or isinstance(expression, (str, int, float, bool)):
        return expression

    if isinstance(expression, list):
        return [evaluate(item, data) for item in expression]

    if not isinstance(expression, dict) or len(expression) != 1:
        raise ValueError("A JSON Logic expression must contain exactly one operator.")

    operator, raw_args = next(iter(expression.items()))
    args = raw_args if isinstance(raw_args, list) else [raw_args]

    if operator == "var":
        return _resolve_var(args, data)

    if operator == "if":
        if len(args) < 2:
            raise ValueError("if requires at least two arguments.")
        index = 0
        while index + 1 < len(args):
            if _truthy(evaluate(args[index], data)):
                return evaluate(args[index + 1], data)
            index += 2
        return evaluate(args[-1], data) if len(args) % 2 else None

    if operator == "and":
        result = None
        for arg in args:
            result = evaluate(arg, data)
            if not _truthy(result):
                return result
        return result

    if operator == "or":
        result = None
        for arg in args:
            result = evaluate(arg, data)
            if _truthy(result):
                return result
        return result

    if operator in ("!", "!!"):
        if len(args) != 1:
            raise ValueError(f"{operator} requires one argument.")
        result = not _truthy(evaluate(args[0], data))
        return result if operator == "!" else not result

    values = [evaluate(arg, data) for arg in args]

    if operator in ("==", "===", "!=", "!=="):
        if len(values) != 2:
            raise ValueError(f"{operator} requires two arguments.")
        equal = _compare_equal(values[0], values[1], strict=operator in ("===", "!=="))
        return not equal if operator in ("!=", "!==") else equal

    if operator in (">", ">=", "<", "<="):
        if len(values) != 2:
            raise ValueError(f"{operator} requires two arguments.")
        left, right = values
        try:
            if operator == ">":
                return left > right
            if operator == ">=":
                return left >= right
            if operator == "<":
                return left < right
            return left <= right
        except TypeError:
            return False

    if operator == "in":
        if len(values) != 2:
            raise ValueError("in requires two arguments.")
        needle, haystack = values
        try:
            return needle in haystack
        except TypeError:
            return False

    if operator == "cat":
        return "".join(_to_string(value) for value in values)

    if operator in ("+", "-", "*", "/", "%"):
        return _arithmetic(operator, values)

    if operator == "min":
        return min(values)
    if operator == "max":
        return max(values)

    if operator == "substr":
        if len(values) not in (2, 3):
            raise ValueError("substr requires two or three arguments.")
        text = _to_string(values[0])
        start = int(values[1])
        if len(values) == 2:
            return text[start:]
        length = int(values[2])
        return text[start:start + length]

    if operator == "match":
        if len(values) != 2:
            raise ValueError("match requires two arguments.")
        return re.search(_to_string(values[1]), _to_string(values[0])) is not None

    if operator == "merge":
        merged = []
        for value in values:
            if isinstance(value, list):
                merged.extend(value)
            else:
                merged.append(value)
        return merged

    raise ValueError(f"Unsupported JSON Logic operator: {operator}")


def _resolve_var(args, data):
    if not args:
        return data
    path = args[0]
    default = args[1] if len(args) > 1 else None
    if not isinstance(path, str):
        raise ValueError("var path must be a string.")
    current = data
    if path:
        for part in path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
                current = current[int(part)]
            else:
                return default
    return current


def _truthy(value):
    if value is None or value is False:
        return False
    if isinstance(value, (int, float)) and (value == 0 or (isinstance(value, float) and math.isnan(value))):
        return False
    if value == "":
        return False
    return True


def _compare_equal(left, right, strict):
    if strict and type(left) is not type(right):
        return False
    if not strict:
        try:
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return float(left) == float(right)
        except (TypeError, ValueError):
            pass
    return left == right


def _arithmetic(operator, values):
    if not values:
        return 0
    if operator == "+":
        return sum(values)
    if operator == "*":
        result = 1
        for value in values:
            result *= value
        return result
    if operator == "-":
        if len(values) == 1:
            return -values[0]
        result = values[0]
        for value in values[1:]:
            result -= value
        return result
    if operator == "/":
        if len(values) != 2:
            raise ValueError("/ requires two arguments.")
        return values[0] / values[1]
    if operator == "%":
        if len(values) != 2:
            raise ValueError("% requires two arguments.")
        return values[0] % values[1]
    raise ValueError(f"Unsupported arithmetic operator: {operator}")


def _to_string(value):
    if value is None:
        return ""
    return str(value)
