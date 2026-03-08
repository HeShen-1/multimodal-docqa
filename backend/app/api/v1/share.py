from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import get_current_user, get_db
from app.models.response import ApiResponse
from app.models.user import User
from app.schemas.share import ShareAccessRequest, ShareAccessResponse, ShareLinkCreate, ShareLinkResponse
from app.services.permission_service import require_admin
from app.services.share_service import share_service


router = APIRouter(prefix="/share", tags=["share"])
settings = get_settings()


def _resolve_current_user_id(current_user: User | dict) -> str:
    if isinstance(current_user, dict):
        user_id = current_user.get("user_id") or current_user.get("id")
    else:
        user_id = getattr(current_user, "id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="无法识别当前用户")
    return str(user_id)


def _build_share_url(token: str) -> str:
    return f"http://{settings.host}:{settings.port}/api/v1/share/{token}"


def _build_share_link_response(link) -> ShareLinkResponse:
    return ShareLinkResponse(
        id=link.id,
        document_id=link.document_id,
        token=link.token,
        share_url=_build_share_url(link.token),
        has_password=link.password is not None,
        allow_download=link.allow_download,
        expires_at=link.expires_at,
        access_count=link.access_count,
        max_access_count=link.max_access_count,
        created_at=link.created_at,
    )


@router.post("/documents/{document_id}", response_model=ApiResponse, status_code=201)
async def create_share_link(
    document_id: str,
    share_data: ShareLinkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        user_id = _resolve_current_user_id(current_user)
        share_link = await share_service.create_share_link(db, document_id, user_id, share_data)
        return ApiResponse(code=100000, message="创建成功", data=_build_share_link_response(share_link))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/{token}/access", response_model=ApiResponse)
async def access_share_link(
    token: str,
    access_data: ShareAccessRequest,
    db: AsyncSession = Depends(get_db),
):
    has_access, error_msg, share_link = await share_service.verify_share_access(db, token, access_data.password)
    if not has_access or share_link is None:
        raise HTTPException(status_code=403, detail=error_msg or "分享访问失败")

    document = await share_service.get_document(db, share_link.document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在")

    return ApiResponse(
        code=100000,
        message="访问成功",
        data=ShareAccessResponse(
            document_id=share_link.document_id,
            file_name=document.file_name,
            file_size=document.file_size,
            allow_download=share_link.allow_download,
        ),
    )


@router.get("/documents/{document_id}", response_model=ApiResponse)
async def get_document_share_links(
    document_id: str,
    include_expired: bool = Query(False, alias="includeExpired"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        user_id = _resolve_current_user_id(current_user)
        share_links = await share_service.get_document_share_links(
            db=db,
            document_id=document_id,
            user_id=user_id,
            include_expired=include_expired,
        )
        return ApiResponse(
            code=100000,
            message="success",
            data=[_build_share_link_response(link) for link in share_links],
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.delete("/{share_id}", response_model=ApiResponse)
async def revoke_share_link(
    share_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        user_id = _resolve_current_user_id(current_user)
        success = await share_service.revoke_share_link(db, share_id, user_id)
        if not success:
            raise HTTPException(status_code=404, detail="分享链接不存在")
        return ApiResponse(code=100000, message="撤销成功", data=None)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/cleanup", response_model=ApiResponse)
async def cleanup_expired_links(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    count = await share_service.cleanup_expired_links(db)
    return ApiResponse(code=100000, message=f"清理了 {count} 个过期链接", data={"count": count})
