import json

from agent.tools import FUNCTIONS, TOOLS, run_tool


def test_every_tool_has_a_function():
    names = {tool["function"]["name"] for tool in TOOLS}
    assert names == set(FUNCTIONS)


def test_tools_use_openai_format():
    for tool in TOOLS:
        assert tool["type"] == "function"
        assert tool["function"]["name"]
        assert tool["function"]["description"]


def test_required_inputs_are_declared_properties():
    for tool in TOOLS:
        parameters = tool["function"].get("parameters")
        if parameters is None:
            continue
        for name in parameters["required"]:
            assert name in parameters["properties"]


def test_get_specs_has_no_parameters():
    get_specs = next(t for t in TOOLS if t["function"]["name"] == "get_specs")
    assert "parameters" not in get_specs["function"]


def test_recommend_screen_through_tool_layer():
    text, is_error = run_tool("recommend_screen", '{"width_m": 6, "height_m": 3.4, "viewing_distance_m": 3}')
    assert not is_error
    assert json.loads(text)["grid"]["cabinets"] == 100


def test_options_for_resolution_through_tool_layer():
    text, is_error = run_tool("options_for_resolution", '{"target_width_px": 3840, "target_height_px": 2160}')
    assert not is_error
    assert json.loads(text)[0]["pitch_mm"] == 0.625


def test_get_specs_with_empty_arguments():
    text, is_error = run_tool("get_specs", "")
    assert not is_error
    assert len(json.loads(text)["pitches"]) == 5


def test_engine_error_becomes_tool_error():
    text, is_error = run_tool("recommend_screen", '{"width_m": 0.2, "height_m": 3}')
    assert is_error
    assert "smaller than one cabinet" in text


def test_unknown_tool():
    text, is_error = run_tool("make_coffee", "{}")
    assert is_error
    assert "Unknown tool" in text


def test_invalid_json_arguments():
    text, is_error = run_tool("recommend_screen", '{"width_m": 6,')
    assert is_error


def test_arguments_must_be_an_object():
    text, is_error = run_tool("recommend_screen", "[6, 3.4]")
    assert is_error


def test_missing_required_argument():
    text, is_error = run_tool("recommend_screen", '{"width_m": 6}')
    assert is_error


def test_unexpected_argument():
    text, is_error = run_tool("recommend_screen", '{"width_m": 6, "height_m": 3.4, "colour": "red"}')
    assert is_error