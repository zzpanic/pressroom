"""
logging_config.py — Structured JSON logging for the Pressroom application.

This file is responsible for:
1. Configuring Python's logging module with JSON-formatted output
2. Providing a get_logger() function that returns a pre-configured logger
3. Adding request_id tracing to every log entry
4. Ensuring log compatibility with Docker logging driver (stdout)

DESIGN RATIONALE:
- JSON formatting enables log aggregation tools (Fluentd, Logstash, Datadog) to parse logs
- Structured logging means every log entry has consistent fields: timestamp, level, logger, message
- Request ID tracing allows correlating all log entries for a single HTTP request
- The logger is configured once at startup in main.py

SPEC REFERENCE: §13 "Logging and Observability"
         §13.1 "Structured Logging — JSON Format"
         §13.2 "Log Levels and Usage"
         §13.3 "Request ID Tracing"

DEPENDENCIES:
- This file is imported by: main.py (startup), all routers (via get_logger())
- No external dependencies — uses only Python standard library

LOG OUTPUT EXAMPLE:
{
    "timestamp": "2026-04-25T10:00:00Z",
    "level": "INFO",
    "logger": "pressroom.routers.papers",
    "message": "Paper loaded successfully",
    "user_id": "user_abc123",
    "request_id": "req_xyz789",
    "slug": "my-paper",
    "duration_ms": 234
}

WHY JSON? Structured logs can be queried and filtered by log aggregation tools.
You can search for all ERROR-level logs for a specific user, or calculate
average response times per endpoint.
"""

import logging
import json
import uuid
from datetime import datetime, timezone
from typing import Any


# ──────────────────────────────────────────────────────────────────
# JSON FORMATTER CLASS
# ──────────────────────────────────────────────────────────────────

class JsonFormatter(logging.Formatter):
    """
    Custom log formatter that outputs JSON instead of plain text.

    This formatter converts Python logging LogRecord objects into
    JSON strings. All standard fields (timestamp, level, logger name)
    are included, plus any extra fields attached to the record.

    USAGE:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)

    FIELDS INCLUDED IN EVERY ENTRY:
    - timestamp: ISO 8601 format with UTC timezone
    - level: Log level name (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - logger: Logger name (usually the module name)
    - message: The log message string
    - request_id: Request trace ID (if attached to record)
    - user_id: Authenticated user ID (if attached to record)

    TODO: Add additional fields based on log level:
    - duration_ms: Added by middleware for timing
    - slug: Added by routers when processing papers
    - exception: Added by error handlers (traceback string)
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format a LogRecord as a JSON string.

        PARAMETERS:
        - record: The logging.LogRecord object containing log metadata
        
        RETURNS:
        - str: JSON string representation of the log entry
        
        LOGIC:
        1. Build a dict with standard fields
        2. Add any extra fields from record.__dict__
        3. Convert to JSON string
        """
        # Build the base log entry dict
        log_entry = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add request_id if present (added by RequestIDMiddleware)
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        # Add user_id if present (added by auth middleware)
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        # Add duration_ms if present (added by timing middleware)
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        # Add exception info if this is an error log
        if record.exc_info:
            log_entry["exception"] = self.formatException(record)
        
        return json.dumps(log_entry)


# ──────────────────────────────────────────────────────────────────
# REQUEST ID MIDDLEWARE (STUB)
# ──────────────────────────────────────────────────────────────────

class RequestIDMiddleware:
    """
    ASGI middleware that stamps every HTTP request with a UUID trace ID.

    On each request:
    - Generates a UUID and stores it in request.state.request_id
    - Returns it in the X-Request-ID response header so clients can correlate logs
    - Does NOT attach the ID to log records automatically — routers that want to
      include it should pass extra={"request_id": request.state.request_id} to
      their logger calls.

    SPEC REFERENCE: §13.3 "Request ID Tracing"
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        from starlette.requests import Request
        from starlette.datastructures import MutableHeaders

        request_id = str(uuid.uuid4())
        scope["state"] = scope.get("state", {})

        request = Request(scope, receive, send)
        request.state.request_id = request_id

        # Intercept the response to inject the header
        async def send_with_header(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.append("X-Request-ID", request_id)
            await send(message)

        await self.app(scope, receive, send_with_header)


# ──────────────────────────────────────────────────────────────────
# LOGGER FACTORY
# ──────────────────────────────────────────────────────────────────

def get_logger(name: str = __name__) -> logging.Logger:
    """
    Get a pre-configured logger instance.

    This function returns a logger that is already configured with:
    - JSON formatter (for structured log output)
    - StreamHandler (for stdout output — Docker captures this)
    - INFO log level (filters out DEBUG, shows INFO+ in production)

    PARAMETERS:
    - name: Logger name — usually __name__ (the current module's dotted path)
            Example: "pressroom.routers.papers" or "pressroom.services.pdf"
    
    RETURNS:
    - logging.Logger: A configured logger instance
    
    USAGE:
        # In any module:
        from logging_config import get_logger
        logger = get_logger(__name__)
        logger.info("Paper loaded", extra={"slug": "my-paper"})
    
    WHY NOT configure logging once in main.py?
    - Each module gets its own named logger
    - Log aggregation tools can filter by logger name
    - Example: Show only PDF-related logs: logger.name == "pressroom.services.pdf"
    
    TODO: Add configuration options:
    - Set log level based on environment (DEBUG in dev, INFO in prod)
    - Add file handler for local debugging (stdout only in production)
    - Add sensitive field redaction (mask tokens, passwords in log output)
    """
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    
    return logger


# ──────────────────────────────────────────────────────────────────
# LOG HELPERS (STUBS)
# ──────────────────────────────────────────────────────────────────

def log_request(request: Any, duration_ms: float = 0) -> None:
    """
    Log a completed HTTP request with method, path, and timing.

    PARAMETERS:
    - request:     A Starlette/FastAPI Request object
    - duration_ms: How long the request took to process (milliseconds)
    """
    logger = get_logger("pressroom.middleware")
    extra: dict = {"duration_ms": duration_ms}

    # Include trace ID if the middleware attached one
    request_id = getattr(getattr(request, "state", None), "request_id", None)
    if request_id:
        extra["request_id"] = request_id

    logger.info(f"{request.method} {request.url.path}", extra=extra)


def log_error(exception: Exception, request: Any = None) -> None:
    """
    Log an exception with full traceback context.

    PARAMETERS:
    - exception: The exception to log
    - request:   Optional Starlette/FastAPI Request for context (method, path, trace ID)
    """
    logger = get_logger("pressroom.exceptions")
    extra: dict = {}

    if request is not None:
        extra["path"] = str(request.url.path)
        request_id = getattr(getattr(request, "state", None), "request_id", None)
        if request_id:
            extra["request_id"] = request_id

    logger.error(str(exception), exc_info=exception, extra=extra)