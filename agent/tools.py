import json
from typing import Any, Callable

from engine import calculator

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "recommend_screen",
            "description": (
                "Find the largest LED cabinet grid that fits a wall, and list every pixel pitch "
                "allowed at the given viewing distance with its resolution. Use this for any "
                "question about what screen fits a wall. All sizes are in metres."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "width_m": {"type": "number", "description": "Wall width in metres"},
                    "height_m": {"type": "number", "description": "Wall height in metres"},
                    "viewing_distance_m": {
                        "type": ["number", "null"],
                        "description": (
                            "Find the largest LED cabinet grid that fits a space, and return its screen size, "
                            "area, diagonal, how much space is left over (an amount only, not where it goes), "
                            "and every pixel pitch allowed at the given viewing distance with its resolution. "
                            "Use this for any question about the screen for a space, including its size, area "
                            "or diagonal. All sizes are in metres."
            ),
                    },
                },
                "required": ["width_m", "height_m"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "options_for_resolution",
            "description": (
                "For a target resolution, list the smallest cabinet grid that reaches it at each "
                "allowed pixel pitch, smallest screen first. Use this when the user asks how to "
                "get a resolution. Full HD = 1920x1080, 4K = 3840x2160, 8K = 7680x4320."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target_width_px": {"type": "integer", "description": "Target width in pixels, e.g. 3840"},
                    "target_height_px": {"type": "integer", "description": "Target height in pixels, e.g. 2160"},
                    "viewing_distance_m": {
                        "type": ["number", "null"],
                        "description": (
                            "Closest viewing distance in metres. Use only if the user stated it. "
                            "If they did not, omit this field or set it to null; never guess a value."
                        )
                    },
                },
                "required": ["target_width_px", "target_height_px"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_specs",
            "description": (
                "Return the product specifications: cabinet size, the available pixel pitches "
                "with pixels per cabinet, and the viewing-distance rule. Use this to answer "
                "questions about what the product offers."
            ),
        },
    },
]

FUNCTIONS: dict[str, Callable[..., Any]] = {
    "recommend_screen": calculator.recommend_screen,
    "options_for_resolution": calculator.options_for_resolution,
    "get_specs": calculator.get_specs,
}


def run_tool(name: str, arguments_json: str) -> tuple[str, bool]:
    """Run a tool the AI asked for. Returns (result_text, is_error)."""
    func = FUNCTIONS.get(name)
    if func is None:
        return f"Unknown tool: {name}", True

    try:
        arguments = json.loads(arguments_json or "{}")
    except json.JSONDecodeError:
        return "Tool arguments were not valid JSON.", True
    if not isinstance(arguments, dict):
        return "Tool arguments must be a JSON object.", True

    try:
        result = func(**arguments)
    except (ValueError, TypeError) as error:
        return str(error), True

    return json.dumps(result), False