from ruleframe.compiler import collect_required_columns, compile_condition, json_pointer


def test_json_pointer_escapes_excel_column_names() -> None:
    assert json_pointer("QA/QC ~ Resolved?") == "/QA~1QC ~0 Resolved?"


def test_compile_condition_uses_json_pointer_vars() -> None:
    compiled = compile_condition(
        {
            "all": [
                {"column": "Selected for QA/QC", "equals": "Yes"},
                {"column": "QA/QC Resolved", "is_blank": True},
            ]
        }
    )
    assert compiled == {
        "and": [
            {"==": [{"var": "/Selected for QA~1QC"}, "Yes"]},
            {"is_blank": [{"var": "/QA~1QC Resolved"}]},
        ]
    }


def test_collect_required_columns_includes_column_to_column_references() -> None:
    columns = collect_required_columns(
        {
            "all": [
                {"column": "Installed Quantity", "equals_column": "Reported Quantity"},
                {
                    "column": "Installation Date",
                    "days_apart_greater_than": {"column": "Date Inspected", "days": 31},
                },
            ]
        }
    )
    assert columns == {
        "Installed Quantity",
        "Reported Quantity",
        "Installation Date",
        "Date Inspected",
    }
