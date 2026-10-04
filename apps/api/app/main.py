"""RippleOps API entry point."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import routes_actions, routes_ai, routes_core, routes_demo, routes_response
from app.api.deps import UserFacingError
from app.config import get_settings
from app.observability import RequestContextMiddleware, configure_logging, request_id_var
from app.services.bom import BomCycleError
from app.services.impact import UnknownPartError
from app.services.scenario import ScenarioInputError
from app.services.store import NotFoundError

configure_logging()
log = logging.getLogger("rippleops.api")

app = FastAPI(title="RippleOps API", version="0.1.0")
app.add_middleware(RequestContextMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=list(get_settings().cors_origins), allow_methods=["*"],
                   allow_headers=["*"])
app.include_router(routes_core.router)
app.include_router(routes_demo.router)
app.include_router(routes_ai.router)
app.include_router(routes_actions.router)
app.include_router(routes_response.router)


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status,
                        content={"error": {"code": code, "message": message, "request_id": request_id_var.get()}})


@app.exception_handler(UserFacingError)
async def _user_error(_: Request, exc: UserFacingError):
    return _error(exc.status_code, exc.code, exc.message)


@app.exception_handler(UnknownPartError)
async def _unknown_part(_: Request, exc: UnknownPartError):
    return _error(422, "unknown_part", f"We couldn't find component '{exc.args[0]}' in the product data. "
                                       "Review the extracted information or enter the part manually.")


@app.exception_handler(ScenarioInputError)
async def _scenario_input(_: Request, exc: ScenarioInputError):
    return _error(422, "invalid_scenario", str(exc))


@app.exception_handler(NotFoundError)
async def _not_found(_: Request, exc: NotFoundError):
    return _error(404, "not_found", f"'{exc.args[0]}' was not found. It may have been cleared by Reset Demo.")


@app.exception_handler(BomCycleError)
async def _bom_cycle(_: Request, exc: BomCycleError):
    log.error("bom_cycle", extra={"detail": str(exc), "error_category": "data_integrity"})
    return _error(500, "data_integrity", "The product structure contains a loop, so it cannot be traced.")


@app.exception_handler(RequestValidationError)
async def _validation(_: Request, exc: RequestValidationError):
    fields = sorted({".".join(str(p) for p in e.get("loc", [])[1:]) for e in exc.errors()})
    return _error(422, "invalid_request", "Some fields are missing or invalid: " + ", ".join(f for f in fields if f))


@app.exception_handler(Exception)
async def _unhandled(_: Request, exc: Exception):
    log.exception("unhandled_error", extra={"error_category": type(exc).__name__})
    return _error(500, "internal_error", "Something went wrong while processing this request. Please try again.")
