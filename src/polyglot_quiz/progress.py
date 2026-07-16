from __future__ import annotations

from collections import OrderedDict
from dataclasses import asdict, dataclass
from threading import Lock
from time import time


@dataclass(frozen=True, slots=True)
class ProgressSnapshot:
    request_id: str
    stage: str
    message: str
    percent: int
    done: bool
    failed: bool
    updated_at: float

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class ProgressStore:
    def __init__(self, *, max_entries: int = 200, ttl_seconds: float = 900) -> None:
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._items: OrderedDict[str, ProgressSnapshot] = OrderedDict()
        self._lock = Lock()

    def start(self, request_id: str) -> ProgressSnapshot:
        return self.update(
            request_id,
            stage="queued",
            message="请求已接收，正在准备...",
            percent=2,
        )

    def update(
        self,
        request_id: str,
        *,
        stage: str,
        message: str,
        percent: int,
        done: bool = False,
        failed: bool = False,
    ) -> ProgressSnapshot:
        snapshot = ProgressSnapshot(
            request_id=request_id,
            stage=stage,
            message=message,
            percent=max(0, min(percent, 100)),
            done=done,
            failed=failed,
            updated_at=time(),
        )
        with self._lock:
            self._prune_locked(snapshot.updated_at)
            self._items[request_id] = snapshot
            self._items.move_to_end(request_id)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)
        return snapshot

    def complete(self, request_id: str) -> ProgressSnapshot:
        return self.update(
            request_id,
            stage="complete",
            message="练习生成完成",
            percent=100,
            done=True,
        )

    def fail(self, request_id: str) -> ProgressSnapshot:
        return self.update(
            request_id,
            stage="failed",
            message="生成失败，请查看错误提示",
            percent=100,
            done=True,
            failed=True,
        )

    def get(self, request_id: str) -> ProgressSnapshot | None:
        now = time()
        with self._lock:
            self._prune_locked(now)
            return self._items.get(request_id)

    def _prune_locked(self, now: float) -> None:
        expired = [
            request_id
            for request_id, snapshot in self._items.items()
            if now - snapshot.updated_at > self.ttl_seconds
        ]
        for request_id in expired:
            self._items.pop(request_id, None)
