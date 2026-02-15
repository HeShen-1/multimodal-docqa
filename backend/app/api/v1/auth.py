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


router = APIRouter(prefix="/auth", tags=["auth"])
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
        refresh_token, jti = auth_service.create_refresh_token(token_data)
        
        # 保存 Refresh Token 到数据库
        expires_at = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
        await auth_service.save_refresh_token(
            db=db,
            user_id=str(user.id),
            token=refresh_token,
            jti=jti,
            expires_at=expires_at,
            device_info=request.headers.get("User-Agent"),
            ip_address=request.client.host if request.client else "127.0.0.1"
        )
        
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
async def logout(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    用户登出
    
    撤销用户的所有 Refresh Token
    """
    try:
        user_id = current_user.get("user_id")
        
        # 撤销用户的所有 Refresh Token
        await auth_service.revoke_all_user_tokens(db, user_id)
        
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
        # 验证刷新令牌（从数据库检查）
        payload = await auth_service.verify_refresh_token(db, refresh_data.refresh_token)
        
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


@router.get("/sessions")
async def get_active_sessions(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取当前用户的活跃会话列表
    
    返回所有未过期且未撤销的 Refresh Token 会话
    """
    try:
        user_id = current_user.get("user_id")
        
        sessions = await auth_service.get_user_active_sessions(db, user_id)
        
        return {
            "total": len(sessions),
            "sessions": [
                {
                    "id": str(session.id),
                    "created_at": session.created_at.isoformat(),
                    "last_used_at": session.last_used_at.isoformat() if session.last_used_at else None,
                    "expires_at": session.expires_at.isoformat(),
                    "device_info": session.device_info,
                    "ip_address": session.ip_address
                }
                for session in sessions
            ]
        }
    
    except Exception as e:
        logger.error(f"获取活跃会话失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取活跃会话失败"
        )


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    撤销指定的会话
    
    用于远程登出某个设备的会话
    """
    try:
        user_id = current_user.get("user_id")
        
        # 查询会话
        from app.models.user import RefreshToken
        result = await db.execute(
            select(RefreshToken).where(
                RefreshToken.id == session_id,
                RefreshToken.user_id == user_id
            )
        )
        session = result.scalar_one_or_none()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在"
            )
        
        # 撤销会话
        await auth_service.revoke_refresh_token(db, session.jti)
        
        logger.info(f"会话已撤销: session_id={session_id}, user={current_user.get('username')}")
        
        return {"message": "会话已撤销"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"撤销会话失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="撤销会话失败"
        )

