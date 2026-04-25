"""
task_queue.py — Async task queue for background job processing.

This file is responsible for:
1. Managing a thread-safe async task queue
2. Tracking task status (pending, running, completed, failed)
3. Providing methods to submit tasks and poll their status
4. Integrating with database.py for persistent task storage

DESIGN RATIONALE:
- FastAPI's built-in background tasks are not trackable - this queue adds tracking
- Each task gets a unique UUID that the UI can poll for status updates
- Task results are stored in memory (database.py handles persistence)

SPEC REFERENCE: §10 "Non-Blocking Background Operations"
         §10.1 "UI Must Remain Responsive During PDF Generation"
         §10.2 "Task Polling Endpoint" (/api/status/{task_id})

DEPENDENCIES:
- This file is imported by: routers/publish.py, routers/papers.py (for save_pdf)
- Imports from: database.py (create_task, update_task_status)

TASK LIFECYCLE:
1. User clicks Publish -> router calls task_queue.submit()
2. Task gets ID and 'pending' status -> router returns ID to UI immediately
3. UI polls /api/status/{task_id} every 2 seconds
4. Task runs in background, status updates to 'running' then 'completed'
5. UI shows success message with PDF path

TODO: Implement the TaskQueue class (see module docstring for design)

USAGE IN ROUTERS:
    from services.task_queue import TaskQueue
    task_queue = TaskQueue()

    @router.post("/api/papers/{slug}/publish")
    async def publish_paper(user_id: str = Depends(require_auth), slug: str, body: PublishRequest):
        # Submit background task, return ID immediately
        task_id = await task_queue.submit(
            user_id, "publish",
            services.snapshot.publish_paper, slug, body.version, body.gate
        )
        return {"task_id": task_id}
"""

import asyncio
import logging
import uuid
from typing import Any, Callable, Dict, Optional

from database import create_task, update_task_status, get_connection

logger = logging.getLogger(__name__)


class TaskQueue:
    """
    Async task queue that runs background jobs and tracks them in SQLite.

    Tasks are created with a UUID, stored in the tasks table as 'pending',
    then executed in a background asyncio task.  The UI polls
    /api/status/{task_id} which reads the tasks table for live status.

    INTEGRATION POINTS:
    - Submit tasks from routers/publish.py or any router that needs async work
    - Poll status from the UI via /api/status/{task_id}
    """

    async def submit(
        self,
        user_id: str,
        task_type: str,
        fn: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> str:
        """
        Record a new task in the database and launch it as a background coroutine.

        PARAMETERS:
        - user_id:   The authenticated user's ID (stored with the task for auditing)
        - task_type: Human-readable label e.g. "publish", "pdf_generate" (stored in DB)
        - fn:        Async callable to execute in the background
        - *args, **kwargs: Passed through to fn

        RETURNS:
        - str: Task UUID — return this to the UI immediately so it can start polling

        TASK LIFECYCLE:
        pending  (written here, before fn starts)
        running  (set when fn begins executing)
        completed / failed  (set when fn returns or raises)
        """
        task_id = str(uuid.uuid4())

        # Write the task record before launching so the UI can poll immediately
        await create_task(task_id, user_id)

        # Launch the work in the background — do not await it here
        asyncio.create_task(self._run(task_id, fn, *args, **kwargs))

        logger.info(f"Task {task_id} submitted (type={task_type}, user={user_id})")
        return task_id

    async def _run(self, task_id: str, fn: Callable, *args: Any, **kwargs: Any) -> None:
        """Execute fn and update the task record with the outcome."""
        await update_task_status(task_id, "running")
        try:
            result = await fn(*args, **kwargs)
            # result must be JSON-serialisable; wrap scalars in a dict if needed
            if not isinstance(result, dict):
                result = {"result": result}
            await update_task_status(task_id, "completed", result=result)
            logger.info(f"Task {task_id} completed")
        except Exception as exc:
            logger.error(f"Task {task_id} failed: {exc}", exc_info=True)
            await update_task_status(task_id, "failed", error=str(exc))

    async def get_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Return the current status record for a task, or None if not found.

        RETURNS dict with keys: task_id, user_id, status, result, error,
        created_at, updated_at — matches the tasks table schema.
        """
        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
                ).fetchone()
                return dict(row) if row else None
        except Exception as exc:
            logger.error(f"Database error fetching task {task_id}: {exc}")
            raise RuntimeError(f"Failed to fetch task status: {exc}")