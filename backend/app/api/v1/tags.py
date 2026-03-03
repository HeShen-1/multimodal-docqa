from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.models.response import ApiResponse
from app.schemas.tag import TagCreate, TagUpdate, TagResponse, DocumentTagRequest
from app.services.tag_service import tag_service
from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.utils.helpers import build_pagination_response

router = APIRouter(prefix="/tags", tags=["tags"])


@router.post("", response_model=ApiResponse, status_code=201)
async def create_tag(
    tag_data: TagCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建标签"""
    try:
        tag = await tag_service.create_tag(db, tag_data)
        return ApiResponse(
            code=100000,
            message="创建成功",
            data=TagResponse.model_validate(tag)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=ApiResponse)
async def get_tags(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    keyword: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取标签列表"""
    skip = (page - 1) * page_size
    tags, total = await tag_service.get_tags(db, skip, page_size, keyword)
    
    tag_list = [TagResponse.model_validate(tag) for tag in tags]
    
    return ApiResponse(
        code=100000,
        message="success",
        data=build_pagination_response(tag_list, total, page, page_size)
    )


@router.get("/popular", response_model=ApiResponse)
async def get_popular_tags(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取热门标签"""
    tags = await tag_service.get_popular_tags(db, limit)
    tag_list = [TagResponse.model_validate(tag) for tag in tags]
    
    return ApiResponse(
        code=100000,
        message="success",
        data=tag_list
    )


@router.get("/search", response_model=ApiResponse)
async def search_tags(
    keyword: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """搜索标签（自动补全）"""
    tags = await tag_service.search_tags(db, keyword, limit)
    tag_list = [TagResponse.model_validate(tag) for tag in tags]
    
    return ApiResponse(
        code=100000,
        message="success",
        data=tag_list
    )


@router.get("/{tag_id}", response_model=ApiResponse)
async def get_tag(
    tag_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取标签详情"""
    tag = await tag_service.get_tag(db, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")
    
    return ApiResponse(
        code=100000,
        message="success",
        data=TagResponse.model_validate(tag)
    )


@router.patch("/{tag_id}", response_model=ApiResponse)
async def update_tag(
    tag_id: str,
    tag_data: TagUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新标签"""
    try:
        tag = await tag_service.update_tag(db, tag_id, tag_data)
        if not tag:
            raise HTTPException(status_code=404, detail="标签不存在")
        
        return ApiResponse(
            code=100000,
            message="更新成功",
            data=TagResponse.model_validate(tag)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{tag_id}", response_model=ApiResponse)
async def delete_tag(
    tag_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除标签"""
    success = await tag_service.delete_tag(db, tag_id)
    if not success:
        raise HTTPException(status_code=404, detail="标签不存在")
    
    return ApiResponse(
        code=100000,
        message="删除成功",
        data=None
    )

