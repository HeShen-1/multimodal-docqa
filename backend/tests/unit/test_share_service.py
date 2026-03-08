from types import SimpleNamespace

import pytest

from app.schemas.share import ShareLinkCreate
from app.services.share_service import ShareService


class _ExecuteResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        return self._value


class _FakeDB:
    def __init__(self, document):
        self.document = document
        self.added = []
        self.committed = 0
        self.refreshed = 0

    async def execute(self, _query):
        return _ExecuteResult(self.document)

    def add(self, item):
        self.added.append(item)

    async def commit(self):
        self.committed += 1

    async def refresh(self, _item):
        self.refreshed += 1


@pytest.mark.asyncio
async def test_create_share_link_rejects_non_owner():
    service = ShareService()
    db = _FakeDB(SimpleNamespace(id="doc-1", user_id="owner"))

    with pytest.raises(PermissionError):
        await service.create_share_link(
            db=db,
            document_id="doc-1",
            user_id="other-user",
            share_data=ShareLinkCreate(expires_in_hours=24, allow_download=True),
        )

    assert db.added == []


@pytest.mark.asyncio
async def test_get_document_share_links_rejects_non_owner():
    service = ShareService()
    db = _FakeDB(SimpleNamespace(id="doc-1", user_id="owner"))

    with pytest.raises(PermissionError):
        await service.get_document_share_links(
            db=db,
            document_id="doc-1",
            user_id="other-user",
            include_expired=True,
        )
