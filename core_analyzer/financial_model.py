import subprocess
import sys
from pathlib import Path


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


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m core_analyzer.financial_model <repo_path> [--since-days=N]")
        sys.exit(1)

    repo_path = sys.argv[1]
    since_days = 30

    for arg in sys.argv[2:]:
        if arg.startswith("--since-days="):
            since_days = int(arg.split("=")[1])

    try:
        churn = get_file_churn(repo_path, since_days=since_days)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

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
