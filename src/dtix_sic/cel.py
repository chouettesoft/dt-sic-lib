"""CEL expression evaluation using the external cel-python runtime."""

from functools import lru_cache


def _cel_runtime():
    try:
        import celpy
    except ImportError as exc:
        raise RuntimeError(
            "CEL support requires the 'cel-python' package. Install the project "
            "dependencies with: python -m pip install -e ."
        ) from exc
    return celpy


@lru_cache(maxsize=256)
def _compile(expression):
    celpy = _cel_runtime()
    environment = celpy.Environment()
    ast = environment.compile(expression)
    return celpy, environment.program(ast)


def evaluate_cel(expression, context):
    """Compile (with an in-process cache) and evaluate a CEL expression."""
    if not isinstance(expression, str) or not expression.strip():
        raise ValueError("CEL expression must be a non-empty string.")

    celpy, program = _compile(expression)
    activation = celpy.json_to_cel(context)
    return program.evaluate(activation)


def validate_cel_expression(expression):
    """Compile a CEL expression to verify syntax and return True."""
    if not isinstance(expression, str) or not expression.strip():
        raise ValueError("CEL expression must be a non-empty string.")
    _compile(expression)
    return True


def clear_cel_cache():
    """Clear cached compiled CEL programs, primarily useful for tests/reloads."""
    _compile.cache_clear()
