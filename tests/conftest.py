"""
conftest.py — Pytest configuration and shared fixtures.

This file is responsible for:
1. Configuring pytest settings (markers, plugins)
2. Providing shared test fixtures for database connections, temp directories
3. Setting up test-specific configuration values

DESIGN RATIONALE:
- conftest.py is automatically discovered by pytest
- Fixtures defined here are available to all test files
- Test database uses in-memory SQLite to avoid affecting production data

SPEC REFERENCE: §15 "Testing Strategy"
         §15.1 "Test Framework" (pytest)
         §15.2 "Test Structure" (conftest.py location)

DEPENDENCIES:
- This file is imported by: all test files (auto-discovered by pytest)
- External dependency: pytest (add to requirements.txt when implementing)

TEST EXECUTION:
    # Run all tests
    pytest tests/ -v
    
    # Run specific test file
    pytest tests/test_auth.py -v
    
    # Run with coverage
    pytest tests/ --cov=app --cov-report=html
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import AsyncMock


# ──────────────────────────────────────────────────────────────────
# FIXTURES
# ──────────────────────────────────────────────────────────────────

@pytest.fixture
def temp_dir():
    """
    Create a temporary directory for test files.
    
    This fixture provides an isolated temporary directory that is
    automatically cleaned up after each test.
    
    USAGE:
        def test_something(temp_dir):
            file_path = temp_dir / "test.txt"
            file_path.write_text("hello")
            assert file_path.read_text() == "hello"
    """
    directory = tempfile.mkdtemp()
    try:
        yield Path(directory)
    finally:
        shutil.rmtree(directory, ignore_errors=True)


@pytest.fixture
def mock_config(monkeypatch):
    """
    Mock configuration values for testing.
    
    This fixture allows tests to override default config values without
    modifying the actual config.py module.
    
    USAGE:
        def test_something(mock_config):
            mock_config("PDF_ENGINE", "sile")
            # PDF_ENGINE is now "sile" for this test
    """
    class ConfigMock:
        def __init__(self):
            self._overrides = {}
        
        def get(self, key, default=None):
            return self._overrides.get(key, default)
        
        def __call__(self, key, default=None):
            return self._overrides.get(key, default)
        
        def set(self, key, value):
            self._overrides[key] = value
    
    config_mock = ConfigMock()
    
    # Apply overrides to monkeypatched config module
    import sys
    from unittest.mock import MagicMock
    mock_config_module = MagicMock()
    for key in ["PDF_ENGINE", "JWT_SECRET", "DATABASE_PATH"]:
        setattr(mock_config_module, key, getattr(config_mock, key, None))
    
    original_modules = sys.modules.get("config")
    sys.modules["config"] = mock_config_module
    
    yield config_mock
    
    # Restore original config module
    if original_modules:
        sys.modules["config"] = original_modules
    else:
        del sys.modules["config"]


@pytest.fixture
async def test_client():
    """
    Create a test client for the FastAPI application.
    
    This fixture provides an async test client that can be used to
    make HTTP requests to the FastAPI app in tests.
    
    USAGE:
        async def test_api_endpoint(test_client):
            response = await test_client.get("/api/health")
            assert response.status_code == 200
    """
    from unittest.mock import AsyncMock
    
    # Create a mock ASGI app
    class MockApp:
        async def __call__(self, scope, receive, send):
            pass
    
    # TODO: Replace with actual FastAPI test client when app is implemented
    # from fastapi.testclient import TestClient
    # from app.main import app
    # return TestClient(app)
    pass