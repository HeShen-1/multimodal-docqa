"""
缓存管理API - Phase 3
提供缓存监控和管理接口
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from app.models.response import ApiResponse
from app.services.cache_manager import cache_manager
from app.services.permission_service import get_current_user

router = APIRouter(prefix="/cache", tags=["缓存管理"])


@router.get("/stats", response_model=ApiResponse, summary="获取缓存统计信息")
async def get_cache_stats(
    current_user: dict = Depends(get_current_user)
):
    """
    获取Redis缓存统计信息
    
    需要管理员权限
    
    返回信息包括：
    - 内存使用情况
    - 缓存命中率
    - 连接数
    - 运行时间
    """
    try:
        # 检查管理员权限
        if current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="需要管理员权限")
        
        stats = await cache_manager.get_stats()
        
        return ApiResponse(
            code=200,
            message="获取缓存统计成功",
            data=stats
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取缓存统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取缓存统计失败: {str(e)}")


@router.get("/hot-keys", response_model=ApiResponse, summary="获取热点键")
async def get_hot_keys(
    limit: int = Query(10, ge=1, le=100, description="返回数量"),
    current_user: dict = Depends(get_current_user)
):
    """
    获取热点缓存键统计
    
    需要管理员权限
    """
    try:
        # 检查管理员权限
        if current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="需要管理员权限")
        
        hot_keys = await cache_manager.get_hot_keys(limit=limit)
        
        return ApiResponse(
            code=200,
            message="获取热点键成功",
            data={
                "hot_keys": hot_keys,
                "count": len(hot_keys)
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取热点键失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取热点键失败: {str(e)}")


@router.delete("/clear", response_model=ApiResponse, summary="清除缓存")
async def clear_cache(
    cache_type: str = Query(
        "all",
        description="缓存类型: query/document/conversation/user/all"
    ),
    current_user: dict = Depends(get_current_user)
):
    """
    按类型清除缓存
    
    需要管理员权限
    
    支持的类型：
    - query: 查询结果缓存
    - document: 文档缓存
    - conversation: 对话缓存
    - user: 用户缓存
    - all: 所有缓存
    """
    try:
        # 检查管理员权限
        if current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="需要管理员权限")
        
        # 验证缓存类型
        valid_types = ["query", "document", "conversation", "user", "all"]
        if cache_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"无效的缓存类型，支持: {', '.join(valid_types)}"
            )
        
        result = await cache_manager.clear_cache_by_type(cache_type)
        
        return ApiResponse(
            code=200,
            message=result["message"],
            data=result
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"清除缓存失败: {e}")
        raise HTTPException(status_code=500, detail=f"清除缓存失败: {str(e)}")


@router.post("/warmup", response_model=ApiResponse, summary="缓存预热")
async def warmup_cache(
    cache_types: Optional[List[str]] = Query(
        None,
        description="要预热的缓存类型列表"
    ),
    current_user: dict = Depends(get_current_user)
):
    """
    缓存预热 - 提前加载热点数据
    
    需要管理员权限
    
    支持的类型：
    - config: 配置信息
    """
    try:
        # 检查管理员权限
        if current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="需要管理员权限")
        
        result = await cache_manager.warmup_cache(cache_types)
        
        return ApiResponse(
            code=200,
            message=result["message"],
            data=result
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"缓存预热失败: {e}")
        raise HTTPException(status_code=500, detail=f"缓存预热失败: {str(e)}")


@router.get("/keys-count", response_model=ApiResponse, summary="获取缓存键数量")
async def get_keys_count(
    current_user: dict = Depends(get_current_user)
):
    """
    获取各类型缓存键数量统计
    
    需要管理员权限
    """
    try:
        # 检查管理员权限
        if current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="需要管理员权限")
        
        counts = await cache_manager.get_cache_keys_count()
        
        return ApiResponse(
            code=200,
            message="获取缓存键数量成功",
            data=counts
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取缓存键数量失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取缓存键数量失败: {str(e)}")


@router.get("/detail/{key}", response_model=ApiResponse, summary="获取缓存详情")
async def get_cache_detail(
    key: str,
    current_user: dict = Depends(get_current_user)
):
    """
    获取指定缓存键的详细信息
    
    需要管理员权限
    """
    try:
        # 检查管理员权限
        if current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="需要管理员权限")
        
        detail = await cache_manager.get_cache_detail(key)
        
        if detail is None:
            raise HTTPException(status_code=404, detail="缓存键不存在")
        
        return ApiResponse(
            code=200,
            message="获取缓存详情成功",
            data=detail
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取缓存详情失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取缓存详情失败: {str(e)}")
