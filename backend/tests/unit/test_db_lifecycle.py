import pytest

from app import dependencies


class FakeEngine:
    def __init__(self):
        self.dispose_calls = 0

    async def dispose(self):
        self.dispose_calls += 1


@pytest.mark.asyncio
async def test_close_engine_disposes_and_resets_globals():
    fake_engine = FakeEngine()
    original_engine = dependencies._engine
    original_session_maker = dependencies._async_session_maker

    dependencies._engine = fake_engine
    dependencies._async_session_maker = object()

    try:
        await dependencies.close_engine()
    finally:
        if dependencies._engine is None:
            dependencies._engine = original_engine
        if dependencies._async_session_maker is None:
            dependencies._async_session_maker = original_session_maker

    assert fake_engine.dispose_calls == 1
    assert dependencies._engine is None
    assert dependencies._async_session_maker is None
