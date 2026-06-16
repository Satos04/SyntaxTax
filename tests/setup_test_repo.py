import subprocess
import sys
import tempfile
from pathlib import Path


def _git(*args: str, cwd: str) -> None:
    subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=True,
    )


def create_test_repo() -> str:
    tmpdir = tempfile.mkdtemp(prefix="syntaxtax_test_repo_")
    repo = Path(tmpdir)

    _git("init", cwd=str(repo))
    _git("config", "user.name", "Test", cwd=str(repo))
    _git("config", "user.email", "test@test.com", cwd=str(repo))

    file_a = repo / "file_a.py"
    file_b = repo / "file_b.py"
    file_txt = repo / "note.txt"

    # Commit 1: add two .py files and a .txt
    file_a.write_text("def hello():\n    pass\n")
    file_b.write_text("x = 1\n")
    file_txt.write_text("not a python file\n")
    _git("add", ".", cwd=str(repo))
    _git("commit", "-m", "first commit", cwd=str(repo))

    # Commit 2: modify only file_a.py
    file_a.write_text("def hello():\n    return 42\n")
    _git("add", ".", cwd=str(repo))
    _git("commit", "-m", "second commit", cwd=str(repo))

    # Commit 3: modify only file_b.py
    file_b.write_text("x = 2\n")
    _git("add", ".", cwd=str(repo))
    _git("commit", "-m", "third commit", cwd=str(repo))

    return str(repo)


def test_get_file_churn() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core_analyzer.financial_model import get_file_churn

    repo_path = create_test_repo()
    churn = get_file_churn(repo_path, since_days=9999)

    assert churn["file_a.py"] == 2, f"Expected 2, got {churn['file_a.py']}"
    assert churn["file_b.py"] == 2, f"Expected 2, got {churn['file_b.py']}"
    assert "note.txt" not in churn, "note.txt should be filtered out"

    print("test_get_file_churn PASSED")
    print(f"  churn: {churn}")


if __name__ == "__main__":
    test_get_file_churn()
