from typing import Optional, List
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from starlette import status


class ErrorDetail(BaseModel):
    field: Optional[str] = None
    message: str
    code: str


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Optional[List[ErrorDetail]] = None


def install_exception_handlers(app):
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        details: List[ErrorDetail] = []
        for err in exc.errors():
            field_path = ".".join([str(x) for x in err.get("loc", []) if x != "body"]) or None
            details.append(
                ErrorDetail(field=field_path, message=err.get("msg", "validation error"), code=err.get("type", "validation_error"))
            )
        body = ErrorResponse(error="ValidationError", message="Invalid request", details=details).model_dump()
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=body)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        body = ErrorResponse(error=exc.__class__.__name__, message=str(exc)).model_dump()
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=body)

