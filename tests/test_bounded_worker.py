from __future__ import annotations

import asyncio
import threading
import unittest

from backend.bounded_worker import BoundedAsyncWorker, WorkerBusyError


class TestBoundedAsyncWorker(unittest.IsolatedAsyncioTestCase):
    async def test_blocking_operation_does_not_block_event_loop(self) -> None:
        worker = BoundedAsyncWorker(max_workers=1)
        self.addCleanup(worker.close)
        started, release = threading.Event(), threading.Event()

        def blocking():
            started.set()
            release.wait(1)
            return "ok"

        task = asyncio.create_task(worker.run(blocking, timeout=1))
        try:
            for _ in range(100):
                if started.is_set():
                    break
                await asyncio.sleep(0.001)
            self.assertTrue(started.is_set())
            await asyncio.sleep(0)
            self.assertFalse(task.done())
            release.set()
            self.assertEqual(await task, "ok")
        finally:
            release.set()

    async def test_timeout_retains_slot_and_releases_on_actual_completion(self) -> None:
        worker = BoundedAsyncWorker(max_workers=1)
        self.addCleanup(worker.close)
        release = threading.Event()
        try:
            with self.assertRaises(asyncio.TimeoutError):
                await worker.run(lambda: release.wait(1), timeout=0.01)
            with self.assertRaises(WorkerBusyError):
                await worker.run(lambda: "must not queue")
            release.set()
            for _ in range(100):
                try:
                    result = await worker.run(lambda: "new work")
                    break
                except WorkerBusyError:
                    await asyncio.sleep(0.001)
            else:
                self.fail("worker slot was not released")
            self.assertEqual(result, "new work")
        finally:
            release.set()

    async def test_cancelled_caller_does_not_allow_unlimited_background_work(self) -> None:
        worker = BoundedAsyncWorker(max_workers=1)
        self.addCleanup(worker.close)
        started, release = threading.Event(), threading.Event()

        def blocking():
            started.set()
            return release.wait(1)

        task = asyncio.create_task(worker.run(blocking))
        try:
            for _ in range(100):
                if started.is_set():
                    break
                await asyncio.sleep(0.001)
            self.assertTrue(started.is_set())
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            with self.assertRaises(WorkerBusyError):
                await worker.run(lambda: "must not queue")
        finally:
            release.set()

    async def test_close_is_idempotent_and_rejects_work(self) -> None:
        worker = BoundedAsyncWorker(max_workers=1)
        worker.close()
        worker.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await worker.run(lambda: "no")

    async def test_operation_failure_releases_capacity(self) -> None:
        worker = BoundedAsyncWorker(max_workers=1)
        self.addCleanup(worker.close)

        def fail():
            raise ValueError("expected failure")

        with self.assertRaises(ValueError):
            await worker.run(fail)
        self.assertEqual(await worker.run(lambda: "ok"), "ok")


if __name__ == "__main__":
    unittest.main()
