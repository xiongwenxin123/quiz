"""Thread-safe state for progressively generated quiz jobs."""

from __future__ import annotations

import json
from copy import deepcopy
from threading import RLock
from time import monotonic
from typing import Any

from .pydantic_compat import BaseModel


class ProgressiveQuizStore:
    def __init__(self, *, ttl_seconds: float = 3600, max_jobs: int = 100) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_jobs = max_jobs
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = RLock()

    def start(self, job_id: str, requested_total: int) -> dict[str, Any]:
        with self._lock:
            self._prune()
            self._jobs[job_id] = {
                "id": job_id,
                "stage": "queued",
                "message": "任务已创建，正在准备文章...",
                "percent": 1,
                "done": False,
                "failed": False,
                "error": None,
                "article": None,
                "analysis": None,
                "vocabulary": [],
                "questions": [],
                "question_errors": [],
                "warnings": [],
                "metadata": None,
                "requested_total": requested_total,
                "updated_at": monotonic(),
            }
            return self._snapshot(job_id)

    def update(self, job_id: str, stage: str, message: str, percent: int) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job["done"]:
                return
            job.update(
                stage=stage,
                message=message,
                percent=max(job["percent"], min(percent, 99)),
                updated_at=monotonic(),
            )

    def publish(self, job_id: str, event: str, payload: object) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            if event == "source":
                job["article"] = _dump(payload)
            elif event == "article" and isinstance(payload, dict):
                job["article"] = _dump(payload.get("article"))
                job["analysis"] = _dump(payload.get("analysis"))
            elif event == "vocabulary":
                job["vocabulary"].append(_dump(payload))
            elif event == "question":
                job["questions"].append(_dump(payload))
            elif event == "question_error":
                job["question_errors"].append(_dump(payload))
            elif event == "complete":
                package = _dump(payload)
                job["metadata"] = package.get("metadata")
                job["warnings"] = package.get("warnings", [])
                job.update(
                    stage="complete",
                    message="学习内容已生成完成",
                    percent=100,
                    done=True,
                    failed=False,
                )
            job["updated_at"] = monotonic()

    def fail(self, job_id: str, error: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.update(
                stage="failed",
                message="生成未能完成",
                done=True,
                failed=True,
                error=error,
                updated_at=monotonic(),
            )

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            self._prune()
            if job_id not in self._jobs:
                return None
            return self._snapshot(job_id)

    def _snapshot(self, job_id: str) -> dict[str, Any]:
        snapshot = deepcopy(self._jobs[job_id])
        snapshot.pop("updated_at", None)
        return snapshot

    def _prune(self) -> None:
        cutoff = monotonic() - self.ttl_seconds
        expired = [
            job_id
            for job_id, job in self._jobs.items()
            if job["updated_at"] < cutoff
        ]
        for job_id in expired:
            self._jobs.pop(job_id, None)
        if len(self._jobs) >= self.max_jobs:
            oldest = sorted(self._jobs, key=lambda item: self._jobs[item]["updated_at"])
            for job_id in oldest[: len(self._jobs) - self.max_jobs + 1]:
                self._jobs.pop(job_id, None)


def _dump(value: object) -> Any:
    if isinstance(value, BaseModel):
        return json.loads(value.model_dump_json())
    if isinstance(value, dict):
        return {key: _dump(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_dump(item) for item in value]
    return value
