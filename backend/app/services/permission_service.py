from functools import wraps
from typing import List, Callable
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from loguru import logger

from app.services.auth_service import auth_service
from app.models.user import UserRole


security = HTTPBearer()


class PermissionService:
    """权限服务"""
    
    @staticmethod
    def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
        """获取当前用户信息"""
        token = credentials.credentials
        payload = auth_service.verify_token(token)
        
        return {
            "user_id": payload.get("sub"),
            "username": payload.get("username"),
            "role": payload.get("role"),
            "email": payload.get("email")
        }
    
    @staticmethod
    def require_roles(allowed_roles: List[str]) -> Callable:
        """角色权限装饰器"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # 从kwargs中获取current_user
                current_user = kwargs.get("current_user")
                
                if not current_user:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="未认证"
                    )
                
                user_role = current_user.get("role")
                
                if user_role not in allowed_roles:
                    logger.warning(f"用户 {current_user.get('username')} 尝试访问需要 {allowed_roles} 权限的资源")
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="权限不足"
                    )
                
                return await func(*args, **kwargs)
            
            return wrapper
        return decorator
    
    @staticmethod
    def check_resource_permission(user_id: str, resource_owner_id: str) -> bool:
        """检查资源权限"""
        return user_id == resource_owner_id
    
    @staticmethod
    def is_admin(current_user: dict) -> bool:
        """检查是否为管理员"""
        return current_user.get("role") == UserRole.ADMIN.value


# 创建全局实例
permission_service = PermissionService()


# 便捷的依赖注入函数
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """获取当前用户（依赖注入）"""
    return permission_service.get_current_user(credentials)


async def get_current_active_user(current_user: dict = Depends(get_current_user)) -> dict:
    """获取当前活跃用户"""
    # 这里可以添加额外的检查，比如用户是否被禁用
    return current_user


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """要求管理员权限"""
    if not permission_service.is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user

