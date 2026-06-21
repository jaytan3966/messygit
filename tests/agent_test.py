"""Drive Agent.run against a simulated Anthropic client.

We replace the SDK client with a FakeClient that returns a preset queue of
responses (text and/or tool_use blocks) and records every messages.create()
call, so we can assert the agent actually executes tools, feeds results back,
handles errors, and respects its iteration cap — all without a network call.
"""

from types import SimpleNamespace

import pytest

from messygit.agent import agent as agent_mod
from messygit.agent.agent import Agent
from messygit.agent.tool import Tool
from messygit.usage import SESSION_USAGE


# --- fakes for the Anthropic SDK surface the agent touches ----------------

class FakeUsage:
    def __init__(self, input_tokens=10, output_tokens=5):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_creation_input_tokens = 0
        self.cache_read_input_tokens = 0


def text_block(text):
    return SimpleNamespace(type="text", text=text)


def tool_use_block(name, tool_input, id="tu_1"):
    return SimpleNamespace(type="tool_use", name=name, input=tool_input, id=id)


def response(*blocks, usage=None):
    return SimpleNamespace(content=list(blocks), usage=usage or FakeUsage())


class FakeMessages:
    def __init__(self, scripted):
        self._scripted = list(scripted)
        self.calls = []  # every kwargs dict passed to create()

    def create(self, **kwargs):
        # The agent mutates one `messages` list in place across iterations, so
        # snapshot it here to capture what was actually sent on *this* call.
        snapshot = dict(kwargs)
        snapshot["messages"] = list(kwargs["messages"])
        self.calls.append(snapshot)
        if not self._scripted:
            raise AssertionError("agent made more API calls than were scripted")
        return self._scripted.pop(0)


class FakeClient:
    def __init__(self, scripted):
        self.messages = FakeMessages(scripted)


# --- test helpers ---------------------------------------------------------

def make_spy_tool(name="read_file", returns="FILE CONTENTS"):
    """A real Tool wrapping a spy fn that records the kwargs it was called with."""
    calls = []

    def fn(**kwargs):
        calls.append(kwargs)
        return returns

    tool = Tool(
        name=name,
        description="spy tool",
        function=fn,
        parameters={"path": {"type": "string"}},
        required=["path"],
    )
    return tool, calls


def last_tool_results(client):
    """The tool_result list the agent sent on its most recent create() call."""
    return client.messages.calls[-1]["messages"][-1]["content"]


@pytest.fixture(autouse=True)
def reset_usage():
    SESSION_USAGE.input = SESSION_USAGE.output = SESSION_USAGE.requests = 0
    SESSION_USAGE.cost = 0.0
    yield


@pytest.fixture
def run_agent(monkeypatch):
    """Patch the agent's SDK dependencies and run it against scripted responses."""
    model = SimpleNamespace(
        id="claude-test", input_cost_per_token=0.0, output_cost_per_token=0.0
    )
    monkeypatch.setattr(agent_mod, "current_model", lambda: model)
    monkeypatch.setattr(agent_mod, "resolve_api_key", lambda: "test-key")

    def _run(scripted, tools, user_input="go", max_iterations=8):
        client = FakeClient(scripted)
        monkeypatch.setattr(agent_mod, "Anthropic", lambda **kwargs: client)
        agent = Agent(
            name="t",
            system_prompt="sys",
            max_iterations=max_iterations,
            tools=tools,
        )
        result = agent.run(user_input)
        return result, client

    return _run


# --- the happy path: no tools, then with tools ----------------------------

def test_returns_text_without_calling_tools(run_agent):
    tool, calls = make_spy_tool()
    result, client = run_agent([response(text_block("just an answer"))], [tool])
    assert result == "just an answer"
    assert calls == []                       # tool never invoked
    assert len(client.messages.calls) == 1   # only one round-trip


def test_executes_tool_then_returns_final_text(run_agent):
    tool, calls = make_spy_tool(returns="print('hi')")
    scripted = [
        response(tool_use_block("read_file", {"path": "x.py"}, id="tu_1")),
        response(text_block("the file prints hi")),
    ]
    result, client = run_agent(scripted, [tool])
    assert calls == [{"path": "x.py"}]       # tool ran with the model's args
    assert result == "the file prints hi"
    assert len(client.messages.calls) == 2


def test_tool_result_is_sent_back_to_model(run_agent):
    tool, _ = make_spy_tool(returns="RESULT-DATA")
    scripted = [
        response(tool_use_block("read_file", {"path": "x.py"}, id="tu_42")),
        response(text_block("done")),
    ]
    _, client = run_agent(scripted, [tool])
    tr = last_tool_results(client)[0]
    assert tr["type"] == "tool_result"
    assert tr["tool_use_id"] == "tu_42"      # id is threaded through correctly
    assert tr["content"] == "RESULT-DATA"
    assert "is_error" not in tr


def test_first_call_sends_user_input_and_tool_schemas(run_agent):
    tool, _ = make_spy_tool()
    _, client = run_agent([response(text_block("ok"))], [tool], user_input="analyze repo")
    first = client.messages.calls[0]
    assert first["messages"][0] == {"role": "user", "content": "analyze repo"}
    assert first["system"] == "sys"
    assert first["tool_choice"] == {"type": "auto"}
    assert first["tools"][0]["name"] == "read_file"
    assert first["tools"][0]["input_schema"]["type"] == "object"


# --- multiple tool calls in one assistant turn ----------------------------

def test_multiple_tool_uses_in_one_turn_all_execute(run_agent):
    tool, calls = make_spy_tool()
    scripted = [
        response(
            tool_use_block("read_file", {"path": "a"}, id="t1"),
            tool_use_block("read_file", {"path": "b"}, id="t2"),
        ),
        response(text_block("both read")),
    ]
    result, client = run_agent(scripted, [tool])
    assert calls == [{"path": "a"}, {"path": "b"}]
    assert [tr["tool_use_id"] for tr in last_tool_results(client)] == ["t1", "t2"]
    assert result == "both read"


# --- error handling -------------------------------------------------------

def test_unknown_tool_returns_error_result_and_continues(run_agent):
    tool, calls = make_spy_tool(name="read_file")
    scripted = [
        response(tool_use_block("does_not_exist", {}, id="tu_x")),
        response(text_block("recovered")),
    ]
    result, client = run_agent(scripted, [tool])
    assert result == "recovered"
    assert calls == []                       # the real tool was never called
    tr = client.messages.calls[1]["messages"][-1]["content"][0]
    assert tr["is_error"] is True
    assert "does_not_exist" in tr["content"]


def test_tool_exception_becomes_error_result(run_agent):
    def boom(**kwargs):
        raise RuntimeError("kaboom")

    tool = Tool(
        name="read_file",
        description="explodes",
        function=boom,
        parameters={"path": {"type": "string"}},
        required=["path"],
    )
    scripted = [
        response(tool_use_block("read_file", {"path": "x"}, id="tu_e")),
        response(text_block("handled")),
    ]
    result, client = run_agent(scripted, [tool])
    assert result == "handled"
    tr = client.messages.calls[1]["messages"][-1]["content"][0]
    assert tr["is_error"] is True
    assert "kaboom" in tr["content"]


# --- iteration cap --------------------------------------------------------

def test_stops_at_max_iterations(run_agent):
    tool, calls = make_spy_tool()
    # The model never yields plain text, so only the cap can end the loop.
    scripted = [
        response(tool_use_block("read_file", {"path": str(i)}, id=f"tu_{i}"))
        for i in range(10)
    ]
    result, client = run_agent(scripted, [tool], max_iterations=3)
    assert len(client.messages.calls) == 3   # never exceeds the cap
    assert len(calls) == 3


# --- usage accounting -----------------------------------------------------

def test_usage_is_recorded_per_api_call(run_agent):
    tool, _ = make_spy_tool()
    scripted = [
        response(tool_use_block("read_file", {"path": "a"}, id="t1"), usage=FakeUsage(7, 3)),
        response(text_block("done"), usage=FakeUsage(4, 2)),
    ]
    run_agent(scripted, [tool])
    assert SESSION_USAGE.requests == 2
    assert SESSION_USAGE.input == 11   # 7 + 4
    assert SESSION_USAGE.output == 5   # 3 + 2
