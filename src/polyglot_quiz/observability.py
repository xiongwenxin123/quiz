from __future__ import annotations

import json
import logging
from contextvars import ContextVar, Token
from typing import Any


_request_id: ContextVar[str] = ContextVar("quiz_request_id", default="-")
_logger = logging.getLogger("uvicorn.error")


def set_request_id(value: str) -> Token[str]:
    return _request_id.set(value)


def reset_request_id(token: Token[str]) -> None:
    _request_id.reset(token)


def get_request_id() -> str:
    return _request_id.get()


def log_event(event: str, *, log_level: int = logging.INFO, **fields: Any) -> None:
    payload = {"event": event, "request_id": get_request_id(), **fields}
    _logger.log(log_level, "quiz_event %s", json.dumps(payload, ensure_ascii=False, default=str))
