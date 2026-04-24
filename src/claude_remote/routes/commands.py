from fastapi import APIRouter, HTTPException
from ..models import CommandRequest, CommandResponse
from ..agent import run_command

router = APIRouter(prefix="/v1", tags=["commands"])


@router.post("/commands", response_model=CommandResponse)
async def create_command(req: CommandRequest) -> CommandResponse:
    try:
        return await run_command(req)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
