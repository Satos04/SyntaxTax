# Guía del Motor de Análisis (`core_analyzer/`)

## Visión General

El directorio `core_analyzer/` es el núcleo de valor de SyntaxTax. Es un motor de análisis
estático y financiero aislado: **no tiene dependencias de red ni conoce la existencia de la
API**. Puede ejecutarse desde la terminal sin levantar el servidor web.

```
core_analyzer/
├── __init__.py
├── parser.py              # Parseo de AST con la librería nativa ast
├── metrics.py             # Métricas: complejidad ciclomática, líneas, antipatrones
└── financial_model.py     # Churn rate de Git + Matriz de Riesgo y coste financiero
```

---

## 1. `parser.py` — Parseo de archivos `.py`

### `parse_file(filepath: str) -> ast.Module | None`

Lee un archivo `.py` como texto UTF-8 y genera su Árbol de Sintaxis Abstracta (AST)
usando `ast.parse()`.

```python
from core_analyzer.parser import parse_file

tree = parse_file("ruta/al/archivo.py")
```

**Manejo de errores:**

| Escenario | Retorno |
|---|---|
| Archivo no encontrado | `None` + mensaje por consola |
| Error de sintaxis | `None` + mensaje con línea y columna |
| Error de codificación | `None` + mensaje descriptivo |

**Uso CLI:**

```bash
python3 -m core_analyzer.parser ruta/al/archivo.py
```

---

## 2. `metrics.py` — Métricas de código

### `compute_complexity(tree: ast.Module) -> dict[str, int]`

Calcula la **Complejidad Ciclomática de McCabe** para cada función en el AST.

**Fórmula:** `M = 1 + número de puntos de decisión`

**Puntos de decisión que incrementan la complejidad:**
- `if` / `elif`
- `while`
- `for` / `async for`
- `except`
- Comprensiones: listas, diccionarios, conjuntos, generadores

**Cualificación de nombres:**
- Funciones anidadas → `outer.inner`
- Métodos de clase → `ClassName.method_name`
- Funciones dentro de métodos → `ClassName.method.inner`

```python
from core_analyzer.parser import parse_file
from core_analyzer.metrics import compute_complexity

tree = parse_file("archivo.py")
scores = compute_complexity(tree)
# {"simple": 1, "medium": 4, "complex": 7}
```

### `compute_line_metrics(tree: ast.Module, filepath: str) -> dict`

Mide líneas por función usando `node.lineno` y `node.end_lineno` del AST, y detecta
antipatrones de código monolítico.

**Umbrales por defecto:** 50 líneas por función, 500 líneas por archivo.

```python
from core_analyzer.metrics import compute_line_metrics

metrics = compute_line_metrics(tree, "archivo.py")
# {
#     "file_lines": 28,
#     "functions": {"simple": 2, "medium": 6, "complex": 16},
#     "alerts": [
#         {"type": "long_function", "target": "complex", "value": 55, "threshold": 50}
#     ],
# }
```

**Uso CLI (muestra complejidad + líneas + antipatrones):**

```bash
python3 -m core_analyzer.metrics ruta/al/archivo.py
```

---

## 3. `financial_model.py` — Historial Git y coste financiero

### `get_file_churn(repo_path: str, since_days: int = 30) -> dict[str, int]`

Ejecuta `git log --since="N days ago" --name-only --pretty=format:` vía `subprocess`
y cuenta las modificaciones por archivo `.py` en el período indicado.

```python
from core_analyzer.financial_model import get_file_churn

churn = get_file_churn("/ruta/al/repo", since_days=30)
# {"core_analyzer/metrics.py": 3, "core_analyzer/parser.py": 2, ...}
```

**Manejo de errores:**

| Escenario | Comportamiento |
|---|---|
| Ruta no existe | `ValueError` |
| No es un repo Git | Retorna `{}` + mensaje |
| `git` no instalado | Retorna `{}` + mensaje |
| Sin commits en el período | Retorna `{}` |

### `compute_financial_impact(repo_path, since_days=30, cost_per_hour=50.0, hours_per_point=0.5, top_n=5) -> dict`

Cruza la complejidad ciclomática con la frecuencia de modificación para calcular
el **coste financiero** de la deuda técnica.

**Fórmula de coste por función crítica:**

```
cost = extra_complexity × churn × hours_per_point × cost_per_hour
```

**Algoritmo:**

1. Obtiene churn rate vía `get_file_churn()`.
2. Itera solo sobre los archivos que Git reportó como modificados.
3. Para cada archivo: parsea el AST, calcula complejidad por función, mide líneas.
4. Clasifica funciones en **clean** (`extra = 0`, sin coste) y **critical** (`extra > 0`).
5. Calcula coste individual por función crítica.
6. Ordena archivos por coste descendente y toma el top N.

**Estructura del reporte:**

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

**Campos del reporte:**

| Campo | Descripción |
|---|---|
| `total_files_analyzed` | Archivos `.py` con churn > 0 que se analizaron |
| `files_with_churn` | Archivos con al menos 1 modificación en el período |
| `total_functions_analyzed` | Suma de funciones en todos los archivos analizados |
| `total_extra_points` | Suma de puntos de complejidad extra (sobre el baseline de 1) |
| `total_cost_eur` | Coste financiero total estimado en euros |
| `top_files` | Archivos con coste > 0, ordenados por coste descendente |
| `file_metadata.total_functions_count` | Total de funciones en el archivo (contexto global) |
| `file_metadata.clean_functions_count` | Funciones sin coste extra (complejidad = 1) |
| `file_metadata.critical_functions_count` | Funciones que contribuyen al coste |
| `critical_functions` | Solo funciones con `extra > 0`, cada una con su desglose |

**Uso CLI:**

```bash
# Modo financial (default) — salida JSON
python3 -m core_analyzer.financial_model . --since-days=30 --cost-per-hour=50

# Modo churn — tabla de modificaciones
python3 -m core_analyzer.financial_model . --mode=churn --since-days=30

# Parámetros avanzados
python3 -m core_analyzer.financial_model . \
    --since-days=90 \
    --cost-per-hour=75 \
    --hours-per-point=0.3 \
    --top-n=10 \
    --mode=financial
```

---

## 4. Flujo de análisis completo

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
    JSON con top_files, critical_functions, coste total
```

---

## 5. Tests

```
tests/
├── __init__.py
├── sample_complexity.py       # 3 funciones para test de complejidad
├── sample_monolithic.py       # Función larga (+50 líneas) para test de antipatrones
├── setup_test_repo.py         # Genera repo Git temporal para test de churn
└── test_financial_impact.py   # Test de cruce complejidad × churn × coste
```

```bash
python3 tests/test_financial_impact.py
python3 tests/setup_test_repo.py
```
