# calculator_tool.py
import ast
import operator
from decimal import Decimal, localcontext, Underflow
from tools.base_tool import BaseTool

SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
}


class CalculatorTool(BaseTool):
    """Safely evaluate a math expression string."""

    name = "calculator"
    description = "Evaluate bounded decimal arithmetic at 50 significant digits. Use scientific_calculator for units, algebra, scientific functions or configurable precision."
    parameters = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Math expression e.g. '(3 + 4) * 2 / 1.5'",
            }
        },
        "required": ["expression"],
    }

    def _safe_eval(self, node, expression):
        if isinstance(node, ast.Constant):
            if (
                isinstance(node.value, bool)
                or not isinstance(node.value, (int, float))
                or abs(node.value) > 1e100
            ):
                raise ValueError("Use finite numeric constants within 1e100")
            value = Decimal(ast.get_source_segment(expression, node))
            if value and value.copy_abs() < Decimal("1e-100"):
                raise ValueError("Use scientific_calculator below 1e-100")
            return +value
        elif isinstance(node, ast.BinOp):
            op_fn = SAFE_OPERATORS.get(type(node.op))
            if op_fn is None:
                raise ValueError(f"Unsupported operator: {node.op}")
            left, right = (
                self._safe_eval(node.left, expression),
                self._safe_eval(node.right, expression),
            )
            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ValueError("Exponent exceeds 100")
            result = op_fn(left, right)
            if isinstance(result, complex) or abs(result) > 1e100:
                raise ValueError(
                    "Result exceeds basic calculator limits; use scientific_calculator"
                )
            return result
        elif isinstance(node, ast.UnaryOp):
            op_fn = SAFE_OPERATORS.get(type(node.op))
            if op_fn is None:
                raise ValueError(f"Unsupported operator: {node.op}")
            return op_fn(self._safe_eval(node.operand, expression))
        else:
            raise ValueError(f"Unsupported expression type: {type(node)}")

    def run(self, **kwargs) -> str:
        expression = kwargs["expression"]
        try:
            if not isinstance(expression, str) or len(expression) > 200:
                raise ValueError("Use at most 200 expression characters")
            tree = ast.parse(expression, mode="eval")
            if sum(1 for _ in ast.walk(tree)) > 64:
                raise ValueError("Expression is too complex")
            with localcontext() as context:
                context.prec = 50
                context.Emax, context.Emin = 100, -100
                context.traps[Underflow] = True
                result = self._safe_eval(tree.body, expression)
                text = format(result.normalize(), "f")
                return text.rstrip("0").rstrip(".") if "." in text else text
        except Exception as e:
            return f"[ERROR] Could not evaluate: {e}"
