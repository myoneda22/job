import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from claude_code_sdk.types import AssistantMessage, ResultMessage, TextBlock

from claude_remote.models import CommandRequest, CommandResponse


def make_text_block(text: str) -> TextBlock:
    return TextBlock(text=text)


def make_assistant_message(text: str) -> AssistantMessage:
    return AssistantMessage(content=[make_text_block(text)], model="claude-sonnet-4-6")


def make_result_message(session_id: str = "sess-1", turns: int = 1) -> ResultMessage:
    return ResultMessage(
        subtype="end_turn",
        duration_ms=100,
        duration_api_ms=80,
        is_error=False,
        num_turns=turns,
        session_id=session_id,
        total_cost_usd=0.001,
    )


async def fake_query(prompt, options):
    yield make_assistant_message("Hello from Claude!")
    yield make_result_message()


@pytest.mark.asyncio
async def test_run_command_basic():
    from claude_remote.agent import run_command

    req = CommandRequest(prompt="Say hello", max_turns=1)

    with patch("claude_remote.agent.query", side_effect=fake_query):
        result = await run_command(req)

    assert result.response == "Hello from Claude!"
    assert result.session_id == "sess-1"
    assert result.turns == 1
    assert result.cost_usd == pytest.approx(0.001)
    assert result.is_error is False
    assert result.stop_reason == "end_turn"


async def fake_query_multi_block(prompt, options):
    msg = AssistantMessage(
        content=[make_text_block("Part 1"), make_text_block(" Part 2")],
        model="claude-sonnet-4-6",
    )
    yield msg
    yield make_result_message(session_id="sess-2", turns=2)


@pytest.mark.asyncio
async def test_run_command_concatenates_text_blocks():
    from claude_remote.agent import run_command

    req = CommandRequest(prompt="Tell me more")

    with patch("claude_remote.agent.query", side_effect=fake_query_multi_block):
        result = await run_command(req)

    assert result.response == "Part 1 Part 2"
    assert result.session_id == "sess-2"
    assert result.turns == 2


async def fake_query_resume(prompt, options):
    assert options.resume == "existing-session"
    yield make_assistant_message("Continued!")
    yield make_result_message(session_id="existing-session")


@pytest.mark.asyncio
async def test_run_command_resumes_session():
    from claude_remote.agent import run_command

    req = CommandRequest(prompt="Continue", session_id="existing-session")

    with patch("claude_remote.agent.query", side_effect=fake_query_resume):
        result = await run_command(req)

    assert result.session_id == "existing-session"
    assert result.response == "Continued!"
