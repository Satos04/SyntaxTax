import ast
import sys

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
        self._current_func: str | None = None
        self._counter: int = 0
        self._class_stack: list[str] = []

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
        qualname = ".".join([*self._class_stack, name]) if self._class_stack else name
        self._current_func = qualname
        self._counter = 1

    def _exit_function(self) -> None:
        if self._current_func:
            self.scores[self._current_func] = self._counter
        self._current_func = None
        self._counter = 0

    def visit(self, node: ast.AST) -> None:
        if isinstance(node, DECISION_NODES) and self._current_func is not None:
            self._counter += 1
        super().visit(node)


def compute_complexity(filepath: str) -> dict[str, int]:
    tree = parse_file(filepath)
    if tree is None:
        return {}
    visitor = CyclomaticComplexityVisitor()
    visitor.visit(tree)
    return visitor.scores


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m core_analyzer.metrics <path_to_py_file>")
        sys.exit(1)

    filepath = sys.argv[1]
    scores = compute_complexity(filepath)

    if not scores:
        print("No functions found or error parsing file.")
        sys.exit(1)

    print("Funciones y su complejidad ciclomática:")
    for func, score in scores.items():
        print(f"  {func}: {score}")
