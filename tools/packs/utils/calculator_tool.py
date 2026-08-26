# calculator_tool.py
import ast
import operator
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
    description = "Evaluate a mathematical expression and return the result."
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

    def _safe_eval(self, node):
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.BinOp):
            op_fn = SAFE_OPERATORS.get(type(node.op))
            if op_fn is None:
                raise ValueError(f"Unsupported operator: {node.op}")
            return op_fn(self._safe_eval(node.left), self._safe_eval(node.right))
        elif isinstance(node, ast.UnaryOp):
            op_fn = SAFE_OPERATORS.get(type(node.op))
            if op_fn is None:
                raise ValueError(f"Unsupported operator: {node.op}")
            return op_fn(self._safe_eval(node.operand))
        else:
            raise ValueError(f"Unsupported expression type: {type(node)}")

    def run(self, **kwargs) -> str:
        expression = kwargs["expression"]
        try:
            tree = ast.parse(expression, mode="eval")
            result = self._safe_eval(tree.body)
            return str(result)
        except Exception as e:
            return f"[ERROR] Could not evaluate: {e}"
