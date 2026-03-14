"""Tests for planning phase and ask_user tool."""

import os
import tempfile
import pytest

from pyoz.agent import Agent, _PLANNING_KEYWORDS, PLANNING_PROMPT
from pyoz.providers.base import BaseLLMProvider, LLMResponse, ToolCall


class MockProvider(BaseLLMProvider):
    """Mock LLM provider for testing."""

    def __init__(self, responses: list[LLMResponse] | None = None):
        super().__init__(api_key="test", model="mock-model")
        self.responses = responses or []
        self._call_index = 0
        self.call_log: list[dict] = []

    @property
    def provider_name(self) -> str:
        return "claude"

    @property
    def model_name(self) -> str:
        return "mock-model"

    def chat(self, messages, tools, system_prompt=None):
        self.call_log.append({
            "messages": messages,
            "tools": tools,
            "system_prompt": system_prompt,
        })
        if self._call_index < len(self.responses):
            resp = self.responses[self._call_index]
            self._call_index += 1
            return resp
        return LLMResponse(text="(no more mock responses)")

    def format_tool_result(self, tool_call_id, result):
        return {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": tool_call_id, "content": result}],
        }

    def format_tool_calls_message(self, response):
        content = []
        if response.text:
            content.append({"type": "text", "text": response.text})
        for tc in response.tool_calls:
            content.append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.name,
                "input": tc.arguments,
            })
        return {"role": "assistant", "content": content}


@pytest.fixture
def tmpdir():
    with tempfile.TemporaryDirectory() as d:
        yield d


class TestNeedsPlanning:
    """Test _needs_planning keyword detection."""

    def test_create_triggers_planning(self, tmpdir):
        provider = MockProvider()
        agent = Agent(provider, work_dir=tmpdir)
        assert agent._needs_planning("create a new Java project")

    def test_build_triggers_planning(self, tmpdir):
        provider = MockProvider()
        agent = Agent(provider, work_dir=tmpdir)
        assert agent._needs_planning("build a REST API in Python")

    def test_setup_triggers_planning(self, tmpdir):
        provider = MockProvider()
        agent = Agent(provider, work_dir=tmpdir)
        assert agent._needs_planning("set up a database connection")

    def test_implement_triggers_planning(self, tmpdir):
        provider = MockProvider()
        agent = Agent(provider, work_dir=tmpdir)
        assert agent._needs_planning("implement user authentication")

    def test_simple_question_no_planning(self, tmpdir):
        provider = MockProvider()
        agent = Agent(provider, work_dir=tmpdir)
        assert not agent._needs_planning("what does this function do?")

    def test_fix_no_planning(self, tmpdir):
        provider = MockProvider()
        agent = Agent(provider, work_dir=tmpdir)
        assert not agent._needs_planning("fix the bug on line 42")

    def test_read_no_planning(self, tmpdir):
        provider = MockProvider()
        agent = Agent(provider, work_dir=tmpdir)
        assert not agent._needs_planning("show me the contents of main.py")

    def test_case_insensitive(self, tmpdir):
        provider = MockProvider()
        agent = Agent(provider, work_dir=tmpdir)
        assert agent._needs_planning("CREATE a new project")
        assert agent._needs_planning("Build an app")


class TestPlanningPhase:
    """Test _run_planning_phase with mock LLM responses."""

    def test_plan_ready_returns_none(self, tmpdir):
        """When LLM says PLAN_READY, no clarification needed."""
        provider = MockProvider([
            LLMResponse(
                text="PLAN_READY: Will create a simple Java app with SQLite",
                input_tokens=50, output_tokens=20,
            ),
        ])
        agent = Agent(provider, work_dir=tmpdir, on_ask_user=lambda q, o: o[0])
        result = agent._run_planning_phase("create a java app with sqlite")
        assert result is None

    def test_asks_user_when_ambiguous(self, tmpdir):
        """When LLM calls ask_user, the callback is invoked and answer returned."""
        asked_questions = []

        def mock_ask_user(question, options):
            asked_questions.append((question, options))
            return "PostgreSQL"

        provider = MockProvider([
            LLMResponse(
                text="NEEDS_INPUT: Database choice is ambiguous",
                tool_calls=[
                    ToolCall(
                        id="tc1",
                        name="ask_user",
                        arguments={
                            "question": "Which database?",
                            "options": ["SQLite", "PostgreSQL", "MySQL"],
                        },
                    ),
                ],
                input_tokens=50, output_tokens=30,
            ),
        ])
        agent = Agent(provider, work_dir=tmpdir, on_ask_user=mock_ask_user)
        result = agent._run_planning_phase("create a database app in java")

        assert result is not None
        assert "PostgreSQL" in result
        assert "Which database?" in result
        assert len(asked_questions) == 1
        assert asked_questions[0][0] == "Which database?"

    def test_multiple_questions(self, tmpdir):
        """LLM can ask multiple clarifying questions."""
        answers = iter(["PostgreSQL", "Gradle"])

        def mock_ask_user(question, options):
            return next(answers)

        provider = MockProvider([
            LLMResponse(
                text="NEEDS_INPUT: Multiple choices needed",
                tool_calls=[
                    ToolCall(
                        id="tc1",
                        name="ask_user",
                        arguments={
                            "question": "Which database?",
                            "options": ["SQLite", "PostgreSQL"],
                        },
                    ),
                    ToolCall(
                        id="tc2",
                        name="ask_user",
                        arguments={
                            "question": "Which build tool?",
                            "options": ["Maven", "Gradle"],
                        },
                    ),
                ],
                input_tokens=50, output_tokens=40,
            ),
        ])
        agent = Agent(provider, work_dir=tmpdir, on_ask_user=mock_ask_user)
        result = agent._run_planning_phase("create a java app")

        assert result is not None
        assert "PostgreSQL" in result
        assert "Gradle" in result

    def test_no_callback_skips_planning(self, tmpdir):
        """If no on_ask_user callback, planning is skipped."""
        provider = MockProvider()
        agent = Agent(provider, work_dir=tmpdir)  # no on_ask_user
        result = agent._run_planning_phase("create a java app")
        assert result is None

    def test_no_tool_calls_returns_none(self, tmpdir):
        """If LLM responds with text only (no PLAN_READY, no tools), returns None."""
        provider = MockProvider([
            LLMResponse(text="I'll just proceed.", input_tokens=50, output_tokens=10),
        ])
        agent = Agent(provider, work_dir=tmpdir, on_ask_user=lambda q, o: o[0])
        result = agent._run_planning_phase("create a java app")
        assert result is None

    def test_planning_uses_planning_prompt(self, tmpdir):
        """Planning phase should use PLANNING_PROMPT as system prompt."""
        provider = MockProvider([
            LLMResponse(text="PLAN_READY: simple task", input_tokens=50, output_tokens=10),
        ])
        agent = Agent(provider, work_dir=tmpdir, on_ask_user=lambda q, o: o[0])
        agent._run_planning_phase("create an app")

        assert len(provider.call_log) == 1
        assert provider.call_log[0]["system_prompt"] == PLANNING_PROMPT

    def test_planning_only_has_ask_user_tool(self, tmpdir):
        """Planning phase should only provide the ask_user tool, not all tools."""
        provider = MockProvider([
            LLMResponse(text="PLAN_READY: simple task", input_tokens=50, output_tokens=10),
        ])
        agent = Agent(provider, work_dir=tmpdir, on_ask_user=lambda q, o: o[0])
        agent._run_planning_phase("create an app")

        tools = provider.call_log[0]["tools"]
        assert len(tools) == 1
        assert tools[0]["name"] == "ask_user"

    def test_planning_tracks_tokens(self, tmpdir):
        """Planning phase token usage should be tracked."""
        provider = MockProvider([
            LLMResponse(text="PLAN_READY: ok", input_tokens=100, output_tokens=50),
            # Second response for the main chat loop
            LLMResponse(text="Done!", input_tokens=200, output_tokens=100),
        ])
        agent = Agent(provider, work_dir=tmpdir, on_ask_user=lambda q, o: o[0])
        agent.chat("create a simple script")

        stats = agent.get_stats()
        # Should include both planning and execution tokens
        assert stats["input_tokens"] == 300
        assert stats["output_tokens"] == 150


class TestAskUserToolExecution:
    """Test ask_user tool during the main execution loop."""

    def test_ask_user_tool_with_callback(self, tmpdir):
        """ask_user tool should invoke the callback and return the answer."""
        provider = MockProvider([
            # LLM calls ask_user during execution
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="tc1",
                        name="ask_user",
                        arguments={
                            "question": "Which port?",
                            "options": ["3000", "8080", "5000"],
                        },
                    ),
                ],
                input_tokens=50, output_tokens=20,
            ),
            # LLM responds after getting the answer
            LLMResponse(text="Using port 8080.", input_tokens=50, output_tokens=10),
        ])

        def mock_ask(q, o):
            return "8080"

        agent = Agent(provider, work_dir=tmpdir, on_ask_user=mock_ask)
        result = agent.chat("run the server")  # doesn't trigger planning ("run" not in keywords)
        assert "8080" in result

    def test_ask_user_tool_without_callback(self, tmpdir):
        """Without callback, ask_user should return a fallback message."""
        provider = MockProvider([
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="tc1",
                        name="ask_user",
                        arguments={
                            "question": "Which port?",
                            "options": ["3000", "8080"],
                        },
                    ),
                ],
                input_tokens=50, output_tokens=20,
            ),
            LLMResponse(text="Using default.", input_tokens=50, output_tokens=10),
        ])
        agent = Agent(provider, work_dir=tmpdir)  # no on_ask_user
        result = agent.chat("run the server")
        assert "default" in result.lower()


class TestChatWithPlanning:
    """Test the full chat flow with planning integrated."""

    def test_planning_enriches_message(self, tmpdir):
        """When planning asks questions, the enriched message is sent to execution."""
        provider = MockProvider([
            # Planning phase response: ask about database
            LLMResponse(
                text="NEEDS_INPUT:",
                tool_calls=[
                    ToolCall(
                        id="tc1",
                        name="ask_user",
                        arguments={
                            "question": "Which database?",
                            "options": ["PostgreSQL", "MySQL"],
                        },
                    ),
                ],
                input_tokens=50, output_tokens=20,
            ),
            # Main execution response
            LLMResponse(text="Created app with PostgreSQL.", input_tokens=100, output_tokens=50),
        ])
        agent = Agent(provider, work_dir=tmpdir, on_ask_user=lambda q, o: "PostgreSQL")
        result = agent.chat("create a database app")

        # The execution call should have the enriched message
        exec_call = provider.call_log[1]
        user_msgs = [m for m in exec_call["messages"] if m["role"] == "user"]
        last_user_msg = user_msgs[-1]["content"]
        assert "PostgreSQL" in last_user_msg
        assert "User clarifications" in last_user_msg

    def test_no_planning_for_simple_tasks(self, tmpdir):
        """Simple tasks should skip planning entirely."""
        provider = MockProvider([
            LLMResponse(text="The function returns 42.", input_tokens=50, output_tokens=20),
        ])
        agent = Agent(provider, work_dir=tmpdir, on_ask_user=lambda q, o: o[0])
        result = agent.chat("what does this function return?")

        # Only one LLM call (no planning)
        assert len(provider.call_log) == 1
        # The system prompt should be the main one, not PLANNING_PROMPT
        assert provider.call_log[0]["system_prompt"] != PLANNING_PROMPT


class TestPlanningKeywords:
    """Test the planning keywords list."""

    def test_keywords_are_lowercase(self):
        for kw in _PLANNING_KEYWORDS:
            assert kw == kw.lower(), f"Keyword '{kw}' should be lowercase"

    def test_has_essential_keywords(self):
        essential = ["create", "build", "setup", "implement", "new project"]
        for kw in essential:
            assert kw in _PLANNING_KEYWORDS, f"Missing essential keyword: '{kw}'"

    def test_planning_prompt_exists(self):
        assert len(PLANNING_PROMPT) > 100
        assert "ask_user" in PLANNING_PROMPT
        assert "PLAN_READY" in PLANNING_PROMPT
        assert "NEEDS_INPUT" in PLANNING_PROMPT
