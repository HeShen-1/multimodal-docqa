from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
from loguru import logger
import redis
import uuid

from app.config import get_settings


class AuthService:
    """认证服务"""
    
    def __init__(self):
        self.settings = get_settings()
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.redis_client = redis.Redis(
            host=self.settings.redis_host,
            port=self.settings.redis_port,
            password=self.settings.redis_password if self.settings.redis_password else None,
            db=self.settings.redis_db,
            decode_responses=True
        )
    
    def hash_password(self, password: str) -> str:
        """加密密码"""
        return self.pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """创建访问令牌"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.settings.access_token_expire_minutes)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "jti": str(uuid.uuid4())  # JWT ID
        })
        
        encoded_jwt = jwt.encode(
            to_encode,
            self.settings.secret_key,
            algorithm=self.settings.algorithm
        )
        
        return encoded_jwt
    
    def create_refresh_token(self, data: Dict[str, Any]) -> str:
        """创建刷新令牌"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=self.settings.refresh_token_expire_days)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "jti": str(uuid.uuid4()),
            "type": "refresh"
        })
        
        encoded_jwt = jwt.encode(
            to_encode,
            self.settings.secret_key,
            algorithm=self.settings.algorithm
        )
        
        return encoded_jwt
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """验证Token"""
        try:
            # 检查Token是否在黑名单中
            if self.is_token_blacklisted(token):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token已失效"
                )
            
            payload = jwt.decode(
                token,
                self.settings.secret_key,
                algorithms=[self.settings.algorithm]
            )
            
            return payload
        
        except JWTError as e:
            logger.error(f"Token验证失败: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的Token"
            )
    
    def add_token_to_blacklist(self, token: str, expires_at: datetime):
        """将Token添加到黑名单"""
        try:
            # 计算过期时间（秒）
            ttl = int((expires_at - datetime.utcnow()).total_seconds())
            
            if ttl > 0:
                # 使用Redis存储黑名单，设置过期时间
                self.redis_client.setex(
                    f"blacklist:{token}",
                    ttl,
                    "1"
                )
                logger.info(f"Token已加入黑名单，过期时间: {ttl}秒")
        
        except Exception as e:
            logger.error(f"添加Token到黑名单失败: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="登出失败"
            )
    
    def is_token_blacklisted(self, token: str) -> bool:
        """检查Token是否在黑名单中"""
        try:
            return self.redis_client.exists(f"blacklist:{token}") > 0
        except Exception as e:
            logger.error(f"检查Token黑名单失败: {str(e)}")
            return False
    
    def get_current_user_id(self, token: str) -> str:
        """从Token中获取用户ID"""
        payload = self.verify_token(token)
        user_id = payload.get("sub")
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的Token"
            )
        
        return user_id
    
    def get_current_user_role(self, token: str) -> str:
        """从Token中获取用户角色"""
        payload = self.verify_token(token)
        role = payload.get("role")
        
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的Token"
            )
        
        return role


# 创建全局实例
auth_service = AuthService()

