from datetime import datetime, timedelta
from typing import Optional

import secrets
from loguru import logger
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.document_db import Document
from app.models.share import ShareLink
from app.schemas.share import ShareLinkCreate
from app.utils.helpers import generate_uuid


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class ShareService:
    def __init__(self):
        self.settings = get_settings()

    def _generate_token(self) -> str:
        return secrets.token_urlsafe(32)

    def _hash_password(self, password: str) -> str:
        return pwd_context.hash(password)

    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    async def get_document(self, db: AsyncSession, document_id: str) -> Optional[Document]:
        result = await db.execute(select(Document).where(Document.id == document_id))
        return result.scalar_one_or_none()

    async def get_owned_document(self, db: AsyncSession, document_id: str, user_id: str) -> Document:
        document = await self.get_document(db, document_id)
        if not document:
            raise ValueError(f"文档不存在: {document_id}")
        if str(document.user_id) != str(user_id):
            raise PermissionError("无权访问该文档的分享信息")
        return document

    async def create_share_link(
        self,
        db: AsyncSession,
        document_id: str,
        user_id: str,
        share_data: ShareLinkCreate,
    ) -> ShareLink:
        await self.get_owned_document(db, document_id, user_id)
        expires_at = datetime.utcnow() + timedelta(hours=share_data.expires_in_hours)
        share_link = ShareLink(
            id=generate_uuid(),
            document_id=document_id,
            token=self._generate_token(),
            password=self._hash_password(share_data.password) if share_data.password else None,
            allow_download=share_data.allow_download,
            expires_at=expires_at,
            max_access_count=share_data.max_access_count,
            created_by=user_id,
            access_count=0,
        )
        db.add(share_link)
        await db.commit()
        await db.refresh(share_link)
        logger.info(f"创建分享链接成功: share_id={share_link.id}, document_id={document_id}, user_id={user_id}")
        return share_link

    async def get_share_link(self, db: AsyncSession, share_id: str) -> Optional[ShareLink]:
        result = await db.execute(select(ShareLink).where(ShareLink.id == share_id))
        return result.scalar_one_or_none()

    async def get_share_link_by_token(self, db: AsyncSession, token: str) -> Optional[ShareLink]:
        result = await db.execute(select(ShareLink).where(ShareLink.token == token))
        return result.scalar_one_or_none()

    async def verify_share_access(
        self,
        db: AsyncSession,
        token: str,
        password: Optional[str] = None,
    ) -> tuple[bool, Optional[str], Optional[ShareLink]]:
        share_link = await self.get_share_link_by_token(db, token)
        if not share_link:
            return False, "分享链接不存在", None
        if datetime.utcnow() > share_link.expires_at:
            return False, "分享链接已过期", None
        if share_link.max_access_count and share_link.access_count >= share_link.max_access_count:
            return False, "分享链接访问次数已达上限", None
        if share_link.password:
            if not password:
                return False, "需要访问密码", None
            if not self._verify_password(password, share_link.password):
                return False, "访问密码错误", None

        share_link.access_count += 1
        await db.commit()
        return True, None, share_link

    async def get_document_share_links(
        self,
        db: AsyncSession,
        document_id: str,
        user_id: str,
        include_expired: bool = False,
    ) -> list[ShareLink]:
        await self.get_owned_document(db, document_id, user_id)
        query = select(ShareLink).where(ShareLink.document_id == document_id)
        if not include_expired:
            query = query.where(ShareLink.expires_at > datetime.utcnow())
        query = query.order_by(ShareLink.created_at.desc())
        result = await db.execute(query)
        return list(result.scalars().all())

    async def revoke_share_link(
        self,
        db: AsyncSession,
        share_id: str,
        user_id: str,
    ) -> bool:
        share_link = await self.get_share_link(db, share_id)
        if not share_link:
            return False
        if str(share_link.created_by) != str(user_id):
            raise PermissionError("无权撤销该分享链接")

        await db.delete(share_link)
        await db.commit()
        logger.info(f"撤销分享链接成功: share_id={share_id}, user_id={user_id}")
        return True

    async def cleanup_expired_links(self, db: AsyncSession) -> int:
        result = await db.execute(select(ShareLink).where(ShareLink.expires_at < datetime.utcnow()))
        expired_links = result.scalars().all()
        count = len(expired_links)
        for link in expired_links:
            await db.delete(link)
        await db.commit()
        logger.info(f"清理过期分享链接: count={count}")
        return count


share_service = ShareService()
