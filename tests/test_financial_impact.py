import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core_analyzer.financial_model import compute_financial_impact
from tests.setup_test_repo import create_test_repo


def test_financial_impact() -> None:
    repo_path = create_test_repo()

    report = compute_financial_impact(
        repo_path,
        since_days=9999,
        cost_per_hour=50.0,
        hours_per_point=0.5,
        top_n=5,
    )

    print(f"  total_files_analyzed: {report['total_files_analyzed']}")
    print(f"  total_cost_eur: {report['total_cost_eur']}")

    # All functions in test repo have complexity 1 → extra=0 → cost=0
    # top_files should be empty
    assert len(report["top_files"]) == 0, f"Expected empty, got {report['top_files']}"

    # file_a.py (has 1 function) + file_b.py (no functions) = 2 files
    assert report["total_files_analyzed"] == 2
    assert report["files_with_churn"] == 2

    # Only file_a.py has a function (def hello → complexity 1)
    assert report["total_functions_analyzed"] == 1
    assert report["total_extra_points"] == 0
    assert report["total_cost_eur"] == 0.0

    assert isinstance(report["top_files"], list)
    assert report["since_days"] == 9999
    assert report["cost_per_hour"] == 50.0
    assert report["hours_per_point"] == 0.5

    print("\ntest_financial_impact PASSED")
    print(f"  report JSON:\n{json.dumps(report, indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    test_financial_impact()
