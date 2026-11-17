import json
from types import SimpleNamespace

import httpx
import pytest
from openai import RateLimitError

from agent.agent import Agent, Provider, standard_only, recent_turns

class FakeMessage:
    """Stands in for the library's message object."""

    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls

    def model_dump(self, exclude_none=False):
        data = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            data["tool_calls"] = [
                {"id": c.id, "type": "function",
                 "function": {"name": c.function.name, "arguments": c.function.arguments}}
                for c in self.tool_calls
            ]
        if exclude_none:
            data = {key: value for key, value in data.items() if value is not None}
        return data


def tool_call(call_id, name, arguments):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


class FakeClient:
    """Returns scripted replies in order, and records every request it receives."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **request):
        self.requests.append(request)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return SimpleNamespace(choices=[SimpleNamespace(message=reply)])


def rate_limit_error():
    response = httpx.Response(429, request=httpx.Request("POST", "https://example.com"))
    return RateLimitError("quota used up", response=response, body=None)


def test_direct_answer_without_tools():
    client = FakeClient([FakeMessage(content="Pixel pitch is the spacing between pixels.")])
    agent = Agent([Provider("gemini", client, "fake-model")])

    answer = agent.ask("What is pixel pitch?")

    assert answer == "Pixel pitch is the spacing between pixels."
    assert [m["role"] for m in agent.messages] == ["user", "assistant"]


def test_tool_call_then_answer():
    client = FakeClient([
        FakeMessage(tool_calls=[tool_call("call_1", "recommend_screen",
                                          '{"width_m": 6, "height_m": 3.4, "viewing_distance_m": 3}')]),
        FakeMessage(content="A 10 x 10 wall fits."),
    ])
    agent = Agent([Provider("gemini", client, "fake-model")])

    answer = agent.ask("6 by 3.4 m wall, 3 m away")

    assert answer == "A 10 x 10 wall fits."
    tool_message = agent.messages[2]
    assert tool_message["role"] == "tool"
    assert tool_message["tool_call_id"] == "call_1"
    assert json.loads(tool_message["content"])["grid"]["cabinets"] == 100
    # The second request sent the tool result back to the model
    assert client.requests[1]["messages"][-1]["role"] == "tool"


def test_tool_error_is_marked_for_the_model():
    client = FakeClient([
        FakeMessage(tool_calls=[tool_call("call_1", "recommend_screen", '{"width_m": 0.2, "height_m": 3}')]),
        FakeMessage(content="That wall is too small."),
    ])
    agent = Agent([Provider("gemini", client, "fake-model")])

    agent.ask("0.2 by 3 m wall")

    assert agent.messages[2]["content"].startswith("ERROR:")


def test_falls_back_to_second_provider():
    failing = FakeClient([rate_limit_error()])
    working = FakeClient([FakeMessage(content="Answer from Groq.")])
    agent = Agent([Provider("gemini", failing, "m"), Provider("groq", working, "m")])

    assert agent.ask("Hello") == "Answer from Groq."


def test_all_providers_failing_leaves_history_clean():
    agent = Agent([Provider("gemini", FakeClient([rate_limit_error()]), "m")])

    with pytest.raises(RuntimeError):
        agent.ask("Hello")
    assert agent.messages == []


def test_stops_after_too_many_tool_rounds():
    replies = [FakeMessage(tool_calls=[tool_call(f"call_{i}", "get_specs", "")]) for i in range(5)]
    agent = Agent([Provider("gemini", FakeClient(replies), "m")])

    answer = agent.ask("Loop forever")

    assert answer.startswith("Sorry")


def test_standard_only_removes_extra_fields():
    history = [{
        "role": "assistant",
        "content": None,
        "extra_content": {"google": {"thought_signature": "abc"}},
        "tool_calls": [{"id": "1", "type": "function", "extra_content": {"x": 1},
                        "function": {"name": "get_specs", "arguments": "{}"}}],
    }]

    cleaned = standard_only(history)

    assert "extra_content" not in cleaned[0]
    assert "extra_content" not in cleaned[0]["tool_calls"][0]


def test_recent_turns_keeps_last_questions_and_their_tool_calls():
    messages = [
        {"role": "user", "content": "q1"}, {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "q2"},
        {"role": "assistant", "tool_calls": [{"id": "c1"}]},
        {"role": "tool", "tool_call_id": "c1", "content": "{}"},
        {"role": "assistant", "content": "a2"},
    ]
    kept = recent_turns(messages, max_turns=1)
    assert kept[0] == {"role": "user", "content": "q2"}
    assert len(kept) == 4