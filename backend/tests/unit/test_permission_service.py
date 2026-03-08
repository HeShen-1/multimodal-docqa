import pytest
from fastapi import HTTPException

from app.services.permission_service import require_admin


@pytest.mark.asyncio
async def test_require_admin_rejects_non_admin():
    with pytest.raises(HTTPException) as exc_info:
        await require_admin({"user_id": "u-1", "role": "user"})

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_admin_allows_admin():
    current_user = await require_admin({"user_id": "u-1", "role": "admin"})
    assert current_user["role"] == "admin"
