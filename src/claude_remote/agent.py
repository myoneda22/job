import asyncio
import os
from claude_code_sdk import query, ClaudeCodeOptions
from claude_code_sdk.types import AssistantMessage, ResultMessage, TextBlock

from .config import settings
from .models import CommandRequest, CommandResponse

_semaphore = asyncio.Semaphore(10)


async def run_command(req: CommandRequest) -> CommandResponse:
    os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key)

    options = ClaudeCodeOptions(
        max_turns=req.max_turns or settings.max_turns,
        system_prompt=req.system_prompt,
        model=settings.model,
        permission_mode=settings.permission_mode,
        resume=req.session_id,
    )

    text_chunks: list[str] = []
    session_id: str = req.session_id or ""
    cost_usd: float | None = None
    turns: int = 0
    stop_reason: str | None = None
    is_error: bool = False

    async with _semaphore:
        async for event in query(prompt=req.prompt, options=options):
            if isinstance(event, AssistantMessage):
                for block in event.content:
                    if isinstance(block, TextBlock):
                        text_chunks.append(block.text)
            elif isinstance(event, ResultMessage):
                session_id = event.session_id
                cost_usd = event.total_cost_usd
                turns = event.num_turns
                is_error = event.is_error
                stop_reason = event.subtype

    return CommandResponse(
        session_id=session_id,
        response="".join(text_chunks),
        cost_usd=cost_usd,
        turns=turns,
        stop_reason=stop_reason,
        is_error=is_error,
    )
