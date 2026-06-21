"""
Calculator tool — safely evaluates mathematical expressions.

Supported: +, -, *, /, **, %, //, round(), abs(), int(), float(),
           sqrt(), log(), sin(), cos(), tan(), pi, e

Usage (in agent response):
    TOOL_CALL: calculator(2 ** 10 + sqrt(144))
"""
import math
import re
from tools.base import Tool

# Whitelist of safe names available in eval context
_SAFE_GLOBALS: dict = {
    "__builtins__": {},
    "abs":   abs,
    "round": round,
    "int":   int,
    "float": float,
    "min":   min,
    "max":   max,
    "sum":   sum,
    "sqrt":  math.sqrt,
    "log":   math.log,
    "log2":  math.log2,
    "log10": math.log10,
    "sin":   math.sin,
    "cos":   math.cos,
    "tan":   math.tan,
    "pi":    math.pi,
    "e":     math.e,
    "pow":   math.pow,
    "ceil":  math.ceil,
    "floor": math.floor,
}

# Block obviously dangerous patterns
_BLOCKED = re.compile(
    r'\b(import|exec|eval|open|os|sys|subprocess|__|\bcompile\b)\b',
    re.IGNORECASE
)


class CalculatorTool(Tool):
    name = "calculator"
    description = (
        "Evaluates a mathematical expression. "
        "Supports: +, -, *, /, **, %, sqrt, log, sin, cos, pi, e, etc. "
        "Example: calculator(2**10 + sqrt(144))"
    )

    def run(self, input_str: str) -> str:
        expr = input_str.strip()
        if _BLOCKED.search(expr):
            return "[Error] Blocked expression — only math operations are allowed."
        try:
            result = eval(expr, _SAFE_GLOBALS, {})  # noqa: S307
            return str(result)
        except ZeroDivisionError:
            return "[Error] Division by zero."
        except Exception as e:
            return f"[Error] Could not evaluate '{expr}': {e}"
