"""
Safe mathematical expression evaluator.

This module NEVER passes raw user input to eval().
Instead it:
  1. Normalises the expression (replaces UI symbols with Python equivalents).
  2. Validates the expression against a strict allow-list of characters.
  3. Builds a restricted namespace that exposes only safe math symbols.
  4. Evaluates the normalised expression inside that namespace via eval().

Supported functions : sin, cos, tan, asin, acos, atan,
                      sinh, cosh, tanh, log, ln, log10,
                      sqrt, cbrt, abs, exp, floor, ceil, round,
                      factorial
Supported constants : pi, e
Supported operators : + - * / % ** ( )
Angle mode          : DEG (degrees) or RAD (radians)
"""

import math
import re
from typing import Any

# ---------------------------------------------------------------------------
# Allowed characters in a normalised expression
# ---------------------------------------------------------------------------
# Letters (for function / constant names), digits, whitespace, and operators.
_ALLOWED_PATTERN = re.compile(
    r"^[0-9a-zA-Z_\s\+\-\*\/\%\(\)\.\,\^]+$"
)

# Maximum expression length (already enforced by Pydantic, but double-check)
MAX_EXPRESSION_LENGTH = 500


# ---------------------------------------------------------------------------
# Safe namespace — only math functions we explicitly allow
# ---------------------------------------------------------------------------
def _build_namespace(mode: str) -> dict[str, Any]:
    """
    Return a dict that is used as the ``globals`` argument to eval().
    Builtins are disabled (__builtins__ = {}).
    """

    def _deg_or_rad(value: float) -> float:
        """Convert value to radians if mode is DEG."""
        return math.radians(value) if mode == "DEG" else value

    # Trig wrappers that honour the current angle mode
    def sin(x: float) -> float:
        return math.sin(_deg_or_rad(x))

    def cos(x: float) -> float:
        return math.cos(_deg_or_rad(x))

    def tan(x: float) -> float:
        return math.tan(_deg_or_rad(x))

    # Inverse trig — result converted back to degrees when in DEG mode
    def asin(x: float) -> float:
        result = math.asin(x)
        return math.degrees(result) if mode == "DEG" else result

    def acos(x: float) -> float:
        result = math.acos(x)
        return math.degrees(result) if mode == "DEG" else result

    def atan(x: float) -> float:
        result = math.atan(x)
        return math.degrees(result) if mode == "DEG" else result

    def cbrt(x: float) -> float:
        """Cube root — works for negative numbers."""
        if x < 0:
            return -((-x) ** (1 / 3))
        return x ** (1 / 3)

    def ln(x: float) -> float:
        """Natural logarithm."""
        if x <= 0:
            raise ValueError("Logarithm undefined for non-positive values")
        return math.log(x)

    def log(x: float) -> float:
        """Base-10 logarithm (matches calculator convention)."""
        if x <= 0:
            raise ValueError("Logarithm undefined for non-positive values")
        return math.log10(x)

    def log10(x: float) -> float:
        if x <= 0:
            raise ValueError("Logarithm undefined for non-positive values")
        return math.log10(x)

    def sqrt(x: float) -> float:
        if x < 0:
            raise ValueError("Square root undefined for negative numbers")
        return math.sqrt(x)

    def factorial(n: float) -> float:
        n_int = int(n)
        if n_int < 0 or n_int != n:
            raise ValueError("Factorial requires a non-negative integer")
        if n_int > 170:
            raise ValueError("Factorial argument too large (max 170)")
        return float(math.factorial(n_int))

    def exp(x: float) -> float:
        return math.exp(x)

    return {
        "__builtins__": {},   # ← disables all Python built-ins
        # Trig
        "sin": sin,
        "cos": cos,
        "tan": tan,
        "asin": asin,
        "acos": acos,
        "atan": atan,
        # Hyperbolic
        "sinh": math.sinh,
        "cosh": math.cosh,
        "tanh": math.tanh,
        # Logarithm / exp
        "log": log,
        "ln": ln,
        "log10": log10,
        "exp": exp,
        # Roots / powers
        "sqrt": sqrt,
        "cbrt": cbrt,
        # Misc
        "abs": abs,
        "floor": math.floor,
        "ceil": math.ceil,
        "round": round,
        "factorial": factorial,
        # Constants
        "pi": math.pi,
        "e": math.e,
    }


# ---------------------------------------------------------------------------
# Expression normaliser
# ---------------------------------------------------------------------------
def _normalise(expression: str) -> str:
    """
    Convert UI-friendly symbols to Python-compatible equivalents.
    """
    expr = expression.strip()

    # Replace Unicode / display symbols
    replacements = [
        ("×", "*"),
        ("÷", "/"),
        ("π", "pi"),
        ("√", "sqrt"),
        # Superscript operators from the frontend
        ("**2", "**2"),   # already valid, keep first so no double-replace
        ("^", "**"),       # caret → Python power operator
        # Common shorthand from button labels
        ("x²", "**2"),
        ("x³", "**3"),
        ("xʸ", "**"),
        ("1/x", "1/"),     # partial — user still types the denominator
        # Make sure 'log' stays log10 (already handled in namespace)
    ]
    for old, new in replacements:
        expr = expr.replace(old, new)

    return expr


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def evaluate_expression(expression: str, mode: str = "DEG") -> float:
    """
    Evaluate a mathematical expression safely.

    Parameters
    ----------
    expression : str
        The expression as typed or sent from the frontend.
    mode : str
        "DEG" (default) or "RAD".

    Returns
    -------
    float
        The numerical result.

    Raises
    ------
    ValueError
        With a human-readable message for any invalid input.
    ZeroDivisionError
        If the expression causes division by zero.
    """
    if not expression or not expression.strip():
        raise ValueError("Expression cannot be empty")

    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise ValueError(
            f"Expression too long (max {MAX_EXPRESSION_LENGTH} characters)"
        )

    # Normalise symbols
    normalised = _normalise(expression)

    # Validate allowed characters
    if not _ALLOWED_PATTERN.match(normalised):
        raise ValueError(
            "Expression contains invalid characters. "
            "Only numbers, standard operators, and known functions are allowed."
        )

    namespace = _build_namespace(mode.upper())

    try:
        result = eval(normalised, namespace)  # noqa: S307 — namespace is locked
    except ZeroDivisionError:
        raise ZeroDivisionError("Division by zero")
    except (NameError, AttributeError) as exc:
        raise ValueError(f"Unknown function or constant: {exc}") from exc
    except (SyntaxError, TypeError) as exc:
        raise ValueError(f"Invalid mathematical expression: {exc}") from exc
    except ValueError:
        raise   # re-raise domain errors from our wrappers
    except Exception as exc:
        raise ValueError(f"Calculation error: {exc}") from exc

    # Reject non-numeric results (inf, nan)
    if not isinstance(result, (int, float)):
        raise ValueError("Expression did not produce a numeric result")
    if math.isnan(result):
        raise ValueError("Result is not a number (NaN)")
    if math.isinf(result):
        raise ValueError("Result is infinity — check your expression")

    return float(result)
