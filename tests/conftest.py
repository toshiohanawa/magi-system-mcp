import sys
import asyncio
import inspect
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def pytest_configure(config: pytest.Config) -> None:
    """Register asyncio marker so tests can mark coroutine functions."""
    config.addinivalue_line("markers", "asyncio: mark test as asyncio coroutine")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "chaos: mark test as chaos test")


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
    """
    Run async test functions via asyncio without external pytest-asyncio dependency.
    """
    testfunction = pyfuncitem.obj
    if not inspect.iscoroutinefunction(testfunction):
        return None

    fixture_kwargs = {name: pyfuncitem.funcargs[name] for name in pyfuncitem._fixtureinfo.argnames or []}  # type: ignore[attr-defined]

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(testfunction(**fixture_kwargs))
        loop.run_until_complete(loop.shutdown_asyncgens())
    finally:
        asyncio.set_event_loop(None)
        loop.close()

    return True
