import ast
import sys
from pathlib import Path

from core_analyzer.parser import parse_file


DECISION_NODES = (
    ast.If,
    ast.While,
    ast.For,
    ast.AsyncFor,
    ast.ListComp,
    ast.DictComp,
    ast.SetComp,
    ast.GeneratorExp,
    ast.ExceptHandler,
)


class CyclomaticComplexityVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.scores: dict[str, int] = {}
        self._func_stack: list[str] = []
        self._class_stack: list[str] = []
        self._counter_stack: list[int] = []
        self._counter: int = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._enter_function(node.name)
        self.generic_visit(node)
        self._exit_function()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._enter_function(node.name)
        self.generic_visit(node)
        self._exit_function()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def _enter_function(self, name: str) -> None:
        self._counter_stack.append(self._counter)
        self._func_stack.append(name)
        self._counter = 1

    def _exit_function(self) -> None:
        qualname = ".".join([*self._class_stack, *self._func_stack])
        self.scores[qualname] = self._counter
        self._func_stack.pop()
        self._counter = self._counter_stack.pop()

    def visit(self, node: ast.AST) -> None:
        if isinstance(node, DECISION_NODES) and self._func_stack:
            self._counter += 1
        super().visit(node)


class FunctionLineVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.functions: dict[str, int] = {}
        self._func_stack: list[str] = []
        self._class_stack: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._push_function(node.name, node.lineno, node.end_lineno)
        self.generic_visit(node)
        self._func_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._push_function(node.name, node.lineno, node.end_lineno)
        self.generic_visit(node)
        self._func_stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def _push_function(self, name: str, lineno: int, end_lineno: int | None) -> None:
        self._func_stack.append(name)
        qualname = ".".join([*self._class_stack, *self._func_stack])
        line_count = (end_lineno - lineno + 1) if end_lineno else 1
        self.functions[qualname] = line_count


def compute_complexity(tree: ast.Module) -> dict[str, int]:
    visitor = CyclomaticComplexityVisitor()
    visitor.visit(tree)
    return visitor.scores


def compute_line_metrics(
    tree: ast.Module,
    filepath: str,
    func_limit: int = 50,
    file_limit: int = 500,
) -> dict:
    file_lines = len(Path(filepath).read_text(encoding="utf-8").splitlines())

    visitor = FunctionLineVisitor()
    visitor.visit(tree)
    functions = visitor.functions

    alerts: list[dict] = []

    for name, lines in functions.items():
        if lines > func_limit:
            alerts.append({
                "type": "long_function",
                "target": name,
                "value": lines,
                "threshold": func_limit,
            })

    if file_lines > file_limit:
        alerts.append({
            "type": "long_file",
            "target": filepath,
            "value": file_lines,
            "threshold": file_limit,
        })

    return {
        "file_lines": file_lines,
        "functions": functions,
        "alerts": alerts,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m core_analyzer.metrics <path_to_py_file>")
        sys.exit(1)

    filepath = sys.argv[1]

    tree = parse_file(filepath)
    if tree is None:
        sys.exit(1)

    scores = compute_complexity(tree)
    line_metrics = compute_line_metrics(tree, filepath)
    file_lines = line_metrics["file_lines"]

    print(f"Archivo: {filepath} ({file_lines} líneas)\n")

    if not scores:
        print("No functions found or error parsing file.\n")
    else:
        print("Funciones y su complejidad ciclomática:")
        for func, score in scores.items():
            func_lines = line_metrics["functions"].get(func, 0)
            print(f"  {func}: score={score}, líneas={func_lines}")
        print()

    alerts = line_metrics["alerts"]
    print("Antipatrones detectados:")
    if not alerts:
        print("  ✅ Ninguno")
    else:
        for alert in alerts:
            if alert["type"] == "long_function":
                print(
                    f"  ⚠ La función '{alert['target']}' tiene "
                    f"{alert['value']} líneas (límite: {alert['threshold']})"
                )
            elif alert["type"] == "long_file":
                print(
                    f"  ⚠ El archivo tiene {alert['value']} líneas "
                    f"(límite: {alert['threshold']})"
                )
