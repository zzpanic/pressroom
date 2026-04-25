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

from typing import Any, Callable, Dict, Optional


class TaskQueue:
    """
    In-memory async task queue for background job processing.

    TODO: Implement the full TaskQueue class (see module docstring for design)

    CURRENT STATE:
    This is a stub - all methods return None or empty values.
    Replace with actual implementation based on the design in the module docstring.

    INTEGRATION POINTS:
    - Submit tasks from routers/publish.py publish_paper() endpoint
    - Submit tasks from routers/papers.py save_paper() when PDF generation is requested
    - Poll status from UI via /api/status/{task_id} endpoint (routers/publish.py)
    """

    async def submit(
        self,
        user_id: str,
        task_type: str,
        fn: Callable,
        *args: Any,
        **kwargs: Any
    ) -> Optional[str]:
        """
        Submit a background task and return its ID immediately.

        PARAMETERS:
        - user_id: The authenticated user's ID
        - task_type: Type of task (e.g., "publish", "pdf_generate", "template_upload")
        - fn: Async callable to execute in background
        - *args, **kwargs: Arguments to pass to the function

        RETURNS:
        - str: Task ID (UUID) that the UI can use for polling

        TODO: Implement:
        1. Generate task_id = str(uuid.uuid4())
        2. Create task record in database with 'pending' status
        3. Start background async task to run fn(*args, **kwargs)
        4. Return task_id immediately (UI can start polling)

        EXAMPLE:
            task_id = await task_queue.submit(
                "user_abc123",
                "publish",
                services.snapshot.publish_paper,
                "my-paper", "v0.1-alpha", "alpha"
            )
            # Returns immediately with task_id like "550e8400-e29b..."
        """
        pass

    async def get_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current task status for polling by the UI.

        PARAMETERS:
        - task_id: The UUID string returned by submit()

        RETURNS:
        - dict with keys: task_id, user_id, status, result, error

        TODO: Implement:
        1. Query database for task record matching task_id
        2. Return dict representation of the record

        UI POLLING EXAMPLE:
            # Every 2 seconds, UI polls:
            fetch('/api/status/550e8400-e29b...')
                .then(r => r.json())
                .then(data => {
                    if (data.status === 'completed') {
                        showSuccess(data.result.pdf_path)
                    } else if (data.status === 'failed') {
                        showError(data.error)
                    }
                })
        """
        pass