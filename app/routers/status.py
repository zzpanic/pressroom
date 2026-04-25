"""
routers/status.py — Async task status polling endpoint.

The UI calls this after submitting a long-running operation (PDF generation,
publish) to check whether it has completed, failed, or is still running.

ENDPOINTS:
    GET /api/status/{task_id}   — return current task status

SPEC REFERENCE: §10.3 "Status Endpoints"
"""

from fastapi import APIRouter, Depends, HTTPException

from auth import check_auth
from models import TaskStatusResponse
from services.task_queue import TaskQueue

router = APIRouter()

# Module-level singleton so routers share the same queue instance.
# Import this from other routers if they need to submit tasks.
task_queue = TaskQueue()


@router.get("/api/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str, _: str = Depends(check_auth)):
    """
    Poll the status of an async background task.

    The task_id is returned immediately when a long-running operation is
    submitted (e.g. PDF generation).  The UI polls this endpoint every few
    seconds until status is "completed" or "failed".

    RETURNS:
        {
            "task_id":  "550e8400-...",
            "status":   "pending" | "running" | "completed" | "failed",
            "result":   { ... } | null,
            "error":    "..." | null
        }

    RAISES:
        HTTP 404 if no task with this ID exists.

    SPEC REFERENCE: §10.3 "Status Endpoints"
    """
    record = await task_queue.get_status(task_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Task '{task_id}' not found. It may have expired or never existed.",
        )

    return TaskStatusResponse(
        task_id=record["task_id"],
        status=record["status"],
        result=record["result"],
        error=record["error"],
    )
