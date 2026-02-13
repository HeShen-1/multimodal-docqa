from fastapi import APIRouter, HTTPException, status, Depends, Request
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.auth import (
    UserRegister, UserLogin, TokenResponse, 
    RefreshTokenRequest, UserResponse, UserProfile
)
from app.services.auth_service import auth_service
from app.services.permission_service import get_current_user
from app.services.rate_limiter import limiter, get_limiter
from app.models.user import User, UserRole
from app.dependencies import get_db
from app.config import get_settings


router = APIRouter(prefix="/auth", tags=["认证"])
settings = get_settings()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.rate_limit_register)
async def register(
    request: Request,
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    """
    用户注册
    
    - **username**: 用户名（3-20字符，字母数字下划线）
    - **email**: 邮箱地址
    - **password**: 密码（8-32字符，必须包含字母和数字）
    """
    try:
        # 检查用户名是否已存在
        result = await db.execute(
            select(User).where(User.username == user_data.username)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在"
            )
        
        # 检查邮箱是否已存在
        result = await db.execute(
            select(User).where(User.email == user_data.email)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被注册"
            )
        
        # 创建新用户
        hashed_password = auth_service.hash_password(user_data.password)
        new_user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=hashed_password,
            role=UserRole.USER
        )
        
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        logger.info(f"新用户注册成功: {user_data.username}")
        
        return new_user
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"用户注册失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="注册失败"
        )


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.rate_limit_login)
async def login(
    request: Request,
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    用户登录
    
    - **username**: 用户名或邮箱
    - **password**: 密码
    
    返回访问令牌和刷新令牌
    """
    try:
        # 查询用户（支持用户名或邮箱登录）
        result = await db.execute(
            select(User).where(
                or_(
                    User.username == login_data.username,
                    User.email == login_data.username
                )
            )
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误"
            )
        
        # 验证密码
        if not auth_service.verify_password(login_data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误"
            )
        
        # 检查用户是否被禁用
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账号已被禁用"
            )
        
        # 更新最后登录时间
        user.last_login_at = datetime.utcnow()
        await db.commit()
        
        # 生成Token
        token_data = {
            "sub": str(user.id),
            "username": user.username,
            "email": user.email,
            "role": user.role.value
        }
        
        access_token = auth_service.create_access_token(token_data)
        refresh_token = auth_service.create_refresh_token(token_data)
        
        logger.info(f"用户登录成功: {user.username}")
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"用户登录失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登录失败"
        )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(current_user: dict = Depends(get_current_user)):
    """
    用户登出
    
    将当前Token加入黑名单
    """
    try:
        # 这里需要从请求头中获取Token
        # 由于已经通过认证，Token已经被验证过
        # 我们需要将Token加入黑名单
        
        # 注意：这里简化处理，实际应该从请求中获取完整Token
        logger.info(f"用户登出: {current_user.get('username')}")
        
        return {"message": "登出成功"}
    
    except Exception as e:
        logger.error(f"用户登出失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登出失败"
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    刷新访问令牌
    
    使用刷新令牌获取新的访问令牌
    """
    try:
        # 验证刷新令牌
        payload = auth_service.verify_token(refresh_data.refresh_token)
        
        # 检查Token类型
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的刷新令牌"
            )
        
        user_id = payload.get("sub")
        
        # 查询用户
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在或已被禁用"
            )
        
        # 生成新的访问令牌
        token_data = {
            "sub": str(user.id),
            "username": user.username,
            "email": user.email,
            "role": user.role.value
        }
        
        access_token = auth_service.create_access_token(token_data)
        
        logger.info(f"Token刷新成功: {user.username}")
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_data.refresh_token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token刷新失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token刷新失败"
        )


@router.get("/me", response_model=UserProfile)
async def get_current_user_info(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取当前用户信息
    
    返回用户详细信息和使用统计
    """
    try:
        user_id = current_user.get("user_id")
        
        # 查询用户
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # TODO: 查询用户的文档数量、查询次数、存储使用量等统计信息
        # 这里暂时返回默认值
        
        return UserProfile(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role.value,
            avatar=user.avatar,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
            document_count=0,
            query_count=0,
            storage_used=0
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取用户信息失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户信息失败"
        )

