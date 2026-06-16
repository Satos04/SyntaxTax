import json
import subprocess
import sys
from pathlib import Path

from core_analyzer.metrics import compute_complexity, compute_line_metrics
from core_analyzer.parser import parse_file


def get_file_churn(repo_path: str, since_days: int = 30) -> dict[str, int]:
    repo = Path(repo_path).resolve()
    if not repo.is_dir():
        raise ValueError(f"Repository path does not exist: {repo}")

    try:
        result = subprocess.run(
            ["git", "log", f"--since={since_days} days ago", "--name-only", "--pretty=format:"],
            capture_output=True,
            text=True,
            cwd=str(repo),
            check=False,
        )
    except FileNotFoundError:
        print("Error: git is not installed or not found in PATH.")
        return {}

    if result.returncode != 0:
        stderr = result.stderr.strip().lower()
        if "not a git repository" in stderr:
            print(f"Error: {repo} is not a git repository.")
        else:
            print(f"Error running git: {result.stderr.strip()}")
        return {}

    churn: dict[str, int] = {}
    for line in result.stdout.strip().splitlines():
        line = line.strip()
        if not line.endswith(".py"):
            continue
        churn[line] = churn.get(line, 0) + 1

    return churn


def compute_financial_impact(
    repo_path: str,
    since_days: int = 30,
    cost_per_hour: float = 50.0,
    hours_per_point: float = 0.5,
    top_n: int = 5,
) -> dict:
    repo = Path(repo_path).resolve()
    if not repo.is_dir():
        raise ValueError(f"Repository path does not exist: {repo}")

    churn_data = get_file_churn(str(repo), since_days=since_days)

    all_files: list[dict] = []
    total_extra_points = 0
    total_functions_analyzed = 0

    for relpath, churn_count in churn_data.items():
        abs_path = repo / relpath

        tree = parse_file(str(abs_path))
        if tree is None:
            continue

        complexity = compute_complexity(tree)
        line_metrics = compute_line_metrics(tree, str(abs_path))
        func_lines = line_metrics.get("functions", {})

        total_functions = len(complexity)
        total_functions_analyzed += total_functions

        critical_functions: list[dict] = []
        clean_count = 0

        total_file_cost = 0.0

        for func_name, func_complexity in complexity.items():
            extra = max(0, func_complexity - 1)
            if extra == 0:
                clean_count += 1
                continue

            func_cost = extra * churn_count * hours_per_point * cost_per_hour
            total_file_cost += func_cost

            critical_functions.append({
                "name": func_name,
                "complexity": func_complexity,
                "extra_complexity": extra,
                "lines": func_lines.get(func_name, 0),
                "cost_eur": round(func_cost, 2),
            })

        total_extra_points += sum(
            max(0, s - 1) for s in complexity.values()
        )

        file_cost_eur = round(total_file_cost, 2)

        all_files.append({
            "file": relpath,
            "cost_eur": file_cost_eur,
            "file_metadata": {
                "total_functions_count": total_functions,
                "clean_functions_count": clean_count,
                "critical_functions_count": len(critical_functions),
            },
            "critical_functions": critical_functions,
        })

    all_files.sort(key=lambda f: f["cost_eur"], reverse=True)
    top_files = [f for f in all_files if f["cost_eur"] > 0][:top_n]
    total_cost = round(sum(f["cost_eur"] for f in all_files), 2)

    return {
        "repo": str(repo),
        "since_days": since_days,
        "cost_per_hour": cost_per_hour,
        "hours_per_point": hours_per_point,
        "total_files_analyzed": len(all_files),
        "files_with_churn": len(all_files),
        "total_functions_analyzed": total_functions_analyzed,
        "total_extra_points": total_extra_points,
        "total_cost_eur": total_cost,
        "top_files": top_files,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m core_analyzer.financial_model <repo_path> [options]")
        print("Options:")
        print("  --mode=MODE          financial (default) | churn")
        print("  --since-days=N       analysis window in days (default: 30)")
        print("  --cost-per-hour=N    hourly rate in EUR (default: 50)")
        print("  --hours-per-point=N  hours per complexity point (default: 0.5)")
        print("  --top-n=N            number of top files to show (default: 5)")
        sys.exit(1)

    repo_path = sys.argv[1]
    since_days = 30
    mode = "financial"
    cost_per_hour = 50.0
    hours_per_point = 0.5
    top_n = 5

    for arg in sys.argv[2:]:
        if arg.startswith("--since-days="):
            since_days = int(arg.split("=")[1])
        elif arg.startswith("--mode="):
            mode = arg.split("=")[1]
        elif arg.startswith("--cost-per-hour="):
            cost_per_hour = float(arg.split("=")[1])
        elif arg.startswith("--hours-per-point="):
            hours_per_point = float(arg.split("=")[1])
        elif arg.startswith("--top-n="):
            top_n = int(arg.split("=")[1])

    try:
        if mode == "churn":
            churn = get_file_churn(repo_path, since_days=since_days)
            if not churn:
                print(
                    f"No se encontraron archivos .py modificados "
                    f"en los últimos {since_days} días en: {repo_path}"
                )
                sys.exit(0)
            print(f"Churn rate (últimos {since_days} días) para archivos .py:")
            for filepath, count in sorted(churn.items(), key=lambda x: x[1], reverse=True):
                print(f"  {filepath}: {count} modificaciones")
            print(f"  total: {len(churn)} archivos .py modificados")
        else:
            report = compute_financial_impact(
                repo_path,
                since_days=since_days,
                cost_per_hour=cost_per_hour,
                hours_per_point=hours_per_point,
                top_n=top_n,
            )
            print(json.dumps(report, indent=2, ensure_ascii=False))
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
