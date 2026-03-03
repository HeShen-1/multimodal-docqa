from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.models.response import ApiResponse
from app.schemas.share import (
    ShareLinkCreate, 
    ShareLinkResponse, 
    ShareAccessRequest,
    ShareAccessResponse
)
from app.services.share_service import share_service
from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.config import get_settings

router = APIRouter(prefix="/share", tags=["share"])
settings = get_settings()


@router.post("/documents/{document_id}", response_model=ApiResponse, status_code=201)
async def create_share_link(
    document_id: str,
    share_data: ShareLinkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建文档分享链接"""
    try:
        share_link = await share_service.create_share_link(
            db, document_id, current_user.id, share_data
        )
        
        # 构建分享URL
        base_url = f"http://{settings.host}:{settings.port}"
        share_url = f"{base_url}/api/v1/share/{share_link.token}"
        
        return ApiResponse(
            code=100000,
            message="创建成功",
            data=ShareLinkResponse(
                id=share_link.id,
                document_id=share_link.document_id,
                token=share_link.token,
                share_url=share_url,
                has_password=share_link.password is not None,
                allow_download=share_link.allow_download,
                expires_at=share_link.expires_at,
                access_count=share_link.access_count,
                max_access_count=share_link.max_access_count,
                created_at=share_link.created_at
            )
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{token}/access", response_model=ApiResponse)
async def access_share_link(
    token: str,
    access_data: ShareAccessRequest,
    db: AsyncSession = Depends(get_db)
):
    """访问分享链接"""
    has_access, error_msg, share_link = await share_service.verify_share_access(
        db, token, access_data.password
    )
    
    if not has_access:
        raise HTTPException(status_code=403, detail=error_msg)
    
    # 获取文档信息（这里简化，实际应从数据库获取）
    from app.api.v1.documents import documents_db
    doc = documents_db.get(share_link.document_id)
    
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    return ApiResponse(
        code=100000,
        message="访问成功",
        data=ShareAccessResponse(
            document_id=share_link.document_id,
            file_name=doc["fileName"],
            file_size=doc["fileSize"],
            allow_download=share_link.allow_download
        )
    )


@router.get("/documents/{document_id}", response_model=ApiResponse)
async def get_document_share_links(
    document_id: str,
    include_expired: bool = Query(False, alias="includeExpired"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取文档的所有分享链接"""
    share_links = await share_service.get_document_share_links(
        db, document_id, include_expired
    )
    
    base_url = f"http://{settings.host}:{settings.port}"
    
    links = [
        ShareLinkResponse(
            id=link.id,
            document_id=link.document_id,
            token=link.token,
            share_url=f"{base_url}/api/v1/share/{link.token}",
            has_password=link.password is not None,
            allow_download=link.allow_download,
            expires_at=link.expires_at,
            access_count=link.access_count,
            max_access_count=link.max_access_count,
            created_at=link.created_at
        )
        for link in share_links
    ]
    
    return ApiResponse(
        code=100000,
        message="success",
        data=links
    )


@router.delete("/{share_id}", response_model=ApiResponse)
async def revoke_share_link(
    share_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """撤销分享链接"""
    try:
        success = await share_service.revoke_share_link(db, share_id, current_user.id)
        if not success:
            raise HTTPException(status_code=404, detail="分享链接不存在")
        
        return ApiResponse(
            code=100000,
            message="撤销成功",
            data=None
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/cleanup", response_model=ApiResponse)
async def cleanup_expired_links(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """清理过期的分享链接（管理员功能）"""
    # TODO: 添加管理员权限检查
    count = await share_service.cleanup_expired_links(db)
    
    return ApiResponse(
        code=100000,
        message=f"清理了 {count} 个过期链接",
        data={"count": count}
    )

