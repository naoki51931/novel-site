import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import author_dashboard_helpers
from app import main


def test_author_dashboard_helpers_are_imported_into_main():
    assert main._table_has_column.__module__ == "app.author_dashboard_helpers"
    assert main._collect_author_dashboard_rows.__module__ == "app.author_dashboard_helpers"
