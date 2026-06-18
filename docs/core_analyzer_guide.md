# Core Analyzer Guide (`core_analyzer/`)

## Overview

The `core_analyzer/` directory is the value kernel of SyntaxTax. It is a standalone static and financial analysis engine: **it has no network dependencies and does not know the API exists**. It can run from the terminal without starting the web server.

```
core_analyzer/
├── __init__.py
├── parser.py              # AST parsing via native ast module
├── metrics.py             # Cyclomatic complexity, line metrics, anti-patterns
└── financial_model.py     # Git churn + risk matrix + financial cost
```

---

## 1. `parser.py` — Parsing `.py` files

### `parse_file(filepath: str) -> ast.Module | None`

Reads a `.py` file as UTF-8 text and generates its Abstract Syntax Tree (AST) using `ast.parse()`.

```python
from core_analyzer.parser import parse_file

tree = parse_file("path/to/file.py")
```

**Error handling:**

| Scenario | Return |
|---|---|
| File not found | `None` + console message |
| Syntax error | `None` + message with line and column |
| Encoding error | `None` + descriptive message |

**CLI usage:**

```bash
python3 -m core_analyzer.parser path/to/file.py
```

---

## 2. `metrics.py` — Code metrics

### `compute_complexity(tree: ast.Module) -> dict[str, int]`

Calculates **McCabe Cyclomatic Complexity** for every function in the AST.

**Formula:** `M = 1 + number of decision points`

**Decision points that increase complexity:**
- `if` / `elif`
- `while`
- `for` / `async for`
- `except`
- Comprehensions: list, dict, set, generator

**Name qualification:**
- Nested functions → `outer.inner`
- Class methods → `ClassName.method_name`
- Functions inside methods → `ClassName.method.inner`

```python
from core_analyzer.parser import parse_file
from core_analyzer.metrics import compute_complexity

tree = parse_file("file.py")
scores = compute_complexity(tree)
# {"simple": 1, "medium": 4, "complex": 7}
```

### `compute_line_metrics(tree: ast.Module, filepath: str) -> dict`

Measures lines per function using `node.lineno` and `node.end_lineno` from the AST, and detects monolithic code anti-patterns.

**Default thresholds:** 50 lines per function, 500 lines per file.

```python
from core_analyzer.metrics import compute_line_metrics

metrics = compute_line_metrics(tree, "file.py")
# {
#     "file_lines": 28,
#     "functions": {"simple": 2, "medium": 6, "complex": 16},
#     "alerts": [
#         {"type": "long_function", "target": "complex", "value": 55, "threshold": 50}
#     ],
# }
```

**CLI usage (shows complexity + lines + alerts):**

```bash
python3 -m core_analyzer.metrics path/to/file.py
```

---

## 3. `financial_model.py` — Git history and financial cost

### `get_file_churn(repo_path: str, since_days: int = 30) -> dict[str, int]`

Runs `git log --since="N days ago" --name-only --pretty=format:` via `subprocess` and counts modifications per `.py` file in the given period.

```python
from core_analyzer.financial_model import get_file_churn

churn = get_file_churn("/path/to/repo", since_days=30)
# {"core_analyzer/metrics.py": 3, "core_analyzer/parser.py": 2, ...}
```

**Error handling:**

| Scenario | Behavior |
|---|---|
| Path does not exist | `ValueError` |
| Not a git repository | Returns `{}` + message |
| `git` not installed | Returns `{}` + message |
| No commits in period | Returns `{}` |

### `compute_financial_impact(repo_path, since_days=30, cost_per_hour=50.0, hours_per_point=0.5, top_n=5) -> dict`

Cross-references cyclomatic complexity with modification frequency to calculate the **financial cost** of technical debt.

**Cost formula per critical function:**

```
cost = extra_complexity × churn × hours_per_point × cost_per_hour
```

**Algorithm:**

1. Get churn rate via `get_file_churn()`
2. Iterate only over files that Git reported as modified
3. For each file: parse AST, calculate per-function complexity, measure lines
4. Classify functions as **clean** (`extra = 0`, no cost) or **critical** (`extra > 0`)
5. Calculate individual cost per critical function
6. Sort files by cost descending and take the top N

**Report structure:**

```json
{
  "repo": "/home/user/repo",
  "since_days": 30,
  "cost_per_hour": 50.0,
  "hours_per_point": 0.5,
  "total_files_analyzed": 10,
  "files_with_churn": 10,
  "total_functions_analyzed": 87,
  "total_extra_points": 45,
  "total_cost_eur": 1425.0,
  "top_files": [
    {
      "file": "core_analyzer/financial_model.py",
      "cost_eur": 700.0,
      "file_metadata": {
        "total_functions_count": 2,
        "clean_functions_count": 0,
        "critical_functions_count": 2
      },
      "critical_functions": [
        {
          "name": "get_file_churn",
          "complexity": 7,
          "extra_complexity": 6,
          "lines": 33,
          "cost_eur": 300.0
        },
        {
          "name": "compute_financial_impact",
          "complexity": 9,
          "extra_complexity": 8,
          "lines": 86,
          "cost_eur": 400.0
        }
      ]
    }
  ]
}
```

**Report fields:**

| Field | Description |
|---|---|
| `total_files_analyzed` | `.py` files with churn > 0 that were analyzed |
| `files_with_churn` | Files with at least 1 modification in the period |
| `total_functions_analyzed` | Sum of functions across all analyzed files |
| `total_extra_points` | Sum of extra complexity points (above baseline of 1) |
| `total_cost_eur` | Estimated total financial cost in EUR |
| `top_files` | Files with cost > 0, sorted by cost descending |
| `file_metadata.total_functions_count` | Total functions in the file (global context) |
| `file_metadata.clean_functions_count` | Functions with no extra cost (complexity = 1) |
| `file_metadata.critical_functions_count` | Functions that contribute to cost |
| `critical_functions` | Only functions with `extra > 0`, each with its breakdown |

**CLI usage:**

```bash
# Financial mode (default) — JSON output
python3 -m core_analyzer.financial_model . --since-days=30 --cost-per-hour=50

# Churn mode — modification table
python3 -m core_analyzer.financial_model . --mode=churn --since-days=30

# Advanced parameters
python3 -m core_analyzer.financial_model . \
    --since-days=90 \
    --cost-per-hour=75 \
    --hours-per-point=0.3 \
    --top-n=10 \
    --mode=financial
```

---

## 4. Complete analysis flow

```
get_file_churn()
    │
    ▼  dict[file → churn]
    │
compute_financial_impact()
    │
    ├── parse_file() → ast.Module
    ├── compute_complexity() → dict[func → score]
    ├── compute_line_metrics() → dict[func → lines, alerts]
    │
    ▼
    JSON with top_files, critical_functions, total_cost
```

---

## 5. Tests

```
tests/
├── __init__.py
├── sample_complexity.py       # 3 functions for complexity testing
├── sample_monolithic.py       # Long function (+50 lines) for anti-pattern testing
├── setup_test_repo.py         # Generates temporary git repo for churn testing
└── test_financial_impact.py   # End-to-end complexity × churn × cost test
```

```bash
python3 tests/test_financial_impact.py
python3 tests/setup_test_repo.py
```
