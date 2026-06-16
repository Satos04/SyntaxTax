import ast
import sys
from pathlib import Path


def parse_file(filepath: str) -> ast.Module | None:
    try:
        source = Path(filepath).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=filepath)
        return tree
    except FileNotFoundError:
        print(f"Error: file not found -> {filepath}")
        return None
    except SyntaxError as e:
        print(f"Syntax error in {filepath}: {e.msg} (line {e.lineno}, col {e.offset})")
        return None
    except UnicodeDecodeError as e:
        print(f"Encoding error in {filepath}: {e}")
        return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m core_analyzer.parser <path_to_py_file>")
        sys.exit(1)

    filepath = sys.argv[1]
    tree = parse_file(filepath)

    if tree is None:
        sys.exit(1)

    print(f"AST parsed successfully: {type(tree).__name__}")
    print(f"Total top-level nodes: {len(tree.body)}")
