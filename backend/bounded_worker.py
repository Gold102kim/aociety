from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading
from typing import Any, Callable, TypeVar


T = TypeVar("T")


class WorkerBusyError(RuntimeError):
    """All worker slots are still occupied by real, possibly timed-out work."""


class BoundedAsyncWorker:
    """Offload blocking operations without accumulating an unbounded queue.

    Cancelling an asyncio caller does not stop a running Python thread. A slot
    belongs to the underlying Future and is released only when that work ends.
    """

    def __init__(self, max_workers: int = 2, name: str = "backend-worker") -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be positive")
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix=name)
        self._slots = threading.BoundedSemaphore(max_workers)
        self._lock = threading.Lock()
        self._closed = False

    async def run(self, function: Callable[..., T], *args: Any, timeout: float = 12.0, **kwargs: Any) -> T:
        with self._lock:
            if self._closed:
                raise RuntimeError("worker is closed")
            if not self._slots.acquire(blocking=False):
                raise WorkerBusyError("worker is busy")
            try:
                future = self._executor.submit(function, *args, **kwargs)
            except Exception:
                self._slots.release()
                raise
        future.add_done_callback(lambda _future: self._slots.release())
        return await asyncio.wait_for(asyncio.wrap_future(future), timeout=timeout)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)
