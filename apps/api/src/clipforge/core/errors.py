"""RFC 7807 problem details and domain exception taxonomy."""

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ProblemDetails(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str | None = None
    code: str
    invalid_params: list[dict[str, Any]] | None = None


class ClipForgeError(Exception):
    status_code: int = 500
    code: str = "INTERNAL_ERROR"
    title: str = "Internal Server Error"

    def __init__(self, detail: str, code: str | None = None, status_code: int | None = None):
        super().__init__(detail)
        self.detail = detail
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class InvalidUrlError(ClipForgeError):
    status_code = 400
    code = "INVALID_URL"
    title = "Invalid Media URL"


class HostNotAllowedError(ClipForgeError):
    status_code = 403
    code = "HOST_NOT_ALLOWED"
    title = "Host Not Allowed"


class VodTooLongError(ClipForgeError):
    status_code = 400
    code = "VOD_TOO_LONG"
    title = "VOD Exceeds Max Duration"


class JobNotFoundError(ClipForgeError):
    status_code = 404
    code = "JOB_NOT_FOUND"
    title = "Job Not Found"


class CandidateNotFoundError(ClipForgeError):
    status_code = 404
    code = "CANDIDATE_NOT_FOUND"
    title = "Candidate Not Found"


class ClipNotFoundError(ClipForgeError):
    status_code = 404
    code = "CLIP_NOT_FOUND"
    title = "Clip Not Found"


class ConflictError(ClipForgeError):
    status_code = 409
    code = "CONFLICT"
    title = "State Conflict"


class StageExecutionError(ClipForgeError):
    status_code = 500
    code = "STAGE_FAILED"
    title = "Pipeline Stage Execution Failed"


async def problem_exception_handler(request: Request, exc: ClipForgeError) -> JSONResponse:
    problem = ProblemDetails(
        type=f"https://clipforge.pt-nct.ai/errors/{exc.code.lower()}",
        title=exc.title,
        status=exc.status_code,
        detail=exc.detail,
        instance=str(request.url),
        code=exc.code,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=problem.model_dump(exclude_none=True),
        headers={"Content-Type": "application/problem+json"},
    )
