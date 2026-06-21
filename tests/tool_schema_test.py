import pytest

from messygit.agent import tools as tools_mod
from messygit.agent.tool import Tool

# Every Tool exposed to the model. The suggestion agent passes the schemas of
# these straight to client.messages.create(tools=[...]), so each must match the
# shape the Anthropic Messages API expects for a tool definition.
ALL_TOOLS = [
    tools_mod.run_git_tool,
    tools_mod.read_file_tool,
    tools_mod.list_directory_tool,
    tools_mod.search_code_tool,
]


@pytest.fixture(params=ALL_TOOLS, ids=lambda t: t.name)
def schema(request):
    return request.param.to_schema()


# --- top-level shape ------------------------------------------------------

def test_schema_has_exactly_the_expected_top_level_keys(schema):
    # Anthropic tool definitions are {name, description, input_schema}.
    # "required" belongs *inside* input_schema, never at the top level.
    assert set(schema) == {"name", "description", "input_schema"}


def test_name_is_nonempty_string(schema):
    assert isinstance(schema["name"], str) and schema["name"]


def test_description_is_nonempty_string(schema):
    # A description is optional to the API but we want every tool to have one.
    assert isinstance(schema["description"], str) and schema["description"].strip()


# --- input_schema (JSON Schema object) ------------------------------------

def test_input_schema_is_a_json_schema_object(schema):
    input_schema = schema["input_schema"]
    assert input_schema["type"] == "object"
    assert isinstance(input_schema["properties"], dict)


def test_every_property_declares_a_type(schema):
    for name, prop in schema["input_schema"]["properties"].items():
        assert isinstance(prop, dict), name
        assert "type" in prop, name


def test_required_is_a_list_referencing_real_properties(schema):
    input_schema = schema["input_schema"]
    if "required" not in input_schema:
        return
    required = input_schema["required"]
    assert isinstance(required, list)
    properties = input_schema["properties"]
    for field in required:
        assert field in properties, f"required field {field!r} missing from properties"


def test_tool_names_are_unique():
    names = [t.name for t in ALL_TOOLS]
    assert len(names) == len(set(names))


# --- to_schema behaviour for the `required` field -------------------------

def test_required_omitted_when_not_set():
    bare = Tool(name="noop", description="does nothing", function=lambda: None)
    assert "required" not in bare.to_schema()["input_schema"]


def test_required_included_when_set():
    t = Tool(
        name="echo",
        description="echo text",
        function=lambda text: text,
        parameters={"text": {"type": "string"}},
        required=["text"],
    )
    schema = t.to_schema()
    assert schema["input_schema"]["required"] == ["text"]
    assert schema["input_schema"]["properties"]["text"]["type"] == "string"
