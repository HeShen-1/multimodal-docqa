from types import SimpleNamespace

import pytest

from app.api.v1 import share as share_module
from app.schemas.share import ShareAccessRequest


@pytest.mark.asyncio
async def test_access_share_link_reads_document_from_persistent_source(monkeypatch):
    share_link = SimpleNamespace(document_id="doc-1", allow_download=True)
    document = SimpleNamespace(file_name="demo.pdf", file_size=2048)
    called = {}

    async def fake_verify_share_access(db, token, password):
        called["token"] = token
        return True, None, share_link

    async def fake_get_document(db, document_id):
        called["document_id"] = document_id
        return document

    monkeypatch.setattr(share_module.share_service, "verify_share_access", fake_verify_share_access)
    monkeypatch.setattr(share_module.share_service, "get_document", fake_get_document)

    response = await share_module.access_share_link(
        token="share-token",
        access_data=ShareAccessRequest(password=None),
        db=object(),
    )

    assert called["token"] == "share-token"
    assert called["document_id"] == "doc-1"
    assert response.data.file_name == "demo.pdf"
    assert response.data.file_size == 2048
