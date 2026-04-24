from pydantic import BaseModel, Field
from typing import Optional


class CommandRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=100_000)
    session_id: Optional[str] = None
    system_prompt: Optional[str] = None
    max_turns: Optional[int] = Field(None, ge=1, le=50)


class CommandResponse(BaseModel):
    session_id: str
    response: str
    cost_usd: Optional[float] = None
    turns: int
    stop_reason: Optional[str] = None
    is_error: bool = False
