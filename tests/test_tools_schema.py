# tests/test_tools_schema.py
"""Lock the tool-schema contract so schema ↔ tool signature drift is caught.

The canonical arg set (TOOL_SCHEMAS) must mirror the tools' exec(args) signatures
in files.py / shell.py / runners.py. A drift here = the next bug (REFLECTION §四:
PLAN self-consistency). These tests pin that contract and the per-provider format.
"""
import pytest
from harness.tools.schema import TOOL_SCHEMAS, for_provider


def test_canonical_arg_names_match_tool_signatures():
    # Must match: read_file{path} write_file{path,content} exec_shell{cmd}
    #             run_tests{} run_lint{} run_typecheck{}
    assert set(TOOL_SCHEMAS) == {"read_file", "write_file", "exec_shell",
                                 "run_tests", "run_lint", "run_typecheck"}
    props = lambda n: set(TOOL_SCHEMAS[n][1].get("properties", {}).keys())
    assert props("read_file") == {"path"}
    assert props("write_file") == {"path", "content"}
    assert props("exec_shell") == {"cmd"}
    assert props("run_tests") == set()
    assert props("run_lint") == set()
    assert props("run_typecheck") == set()


def test_required_fields_present():
    for _name, (_desc, params) in TOOL_SCHEMAS.items():
        assert params["type"] == "object"
        assert "required" in params  # even empty list, for tools with no args


def test_deepseek_format_is_openai_function_shape():
    out = for_provider("deepseek")
    for entry in out:
        assert set(entry) == {"type", "function"}
        assert entry["type"] == "function"
        fn = entry["function"]
        assert set(fn) == {"name", "description", "parameters"}
        assert fn["name"] in TOOL_SCHEMAS


def test_anthropic_format_uses_input_schema():
    out = for_provider("anthropic")
    for entry in out:
        assert set(entry) == {"name", "description", "input_schema"}
        assert entry["name"] in TOOL_SCHEMAS


def test_subset_selection_and_order():
    out = for_provider("deepseek", ["read_file", "run_tests"])
    assert [e["function"]["name"] for e in out] == ["read_file", "run_tests"]


def test_unknown_provider_raises():
    with pytest.raises(ValueError):
        for_provider("openai")  # only deepseek/anthropic wired


def test_unknown_tool_name_raises():
    with pytest.raises(ValueError):
        for_provider("deepseek", ["no_such_tool"])
