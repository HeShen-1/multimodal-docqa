from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis
import uuid
import hashlib
import base64

from app.config import get_settings
from app.models.user import RefreshToken


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
    
    def _prepare_password(self, password: str) -> str:
        """
        预处理密码以避免 bcrypt 72 字节限制
        使用 SHA256 哈希后再进行 base64 编码
        SHA256 输出 32 字节，base64 编码后约 44 字节，远小于 72 字节限制
        """
        # 使用 SHA256 哈希密码（输出固定 32 字节）
        password_hash = hashlib.sha256(password.encode('utf-8')).digest()
        # Base64 编码（32字节 -> 44字符，确保在 72 字节以内）
        prepared = base64.b64encode(password_hash).decode('ascii')
        logger.debug(f"预处理后密码长度: {len(prepared)} 字节")
        return prepared
    
    def hash_password(self, password: str) -> str:
        """加密密码"""
        prepared_password = self._prepare_password(password)
        return self.pwd_context.hash(prepared_password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        prepared_password = self._prepare_password(plain_password)
        return self.pwd_context.verify(prepared_password, hashed_password)
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """创建访问令牌"""
        to_encode = data.copy()
        now = datetime.utcnow()
        
        if expires_delta:
            expire = now + expires_delta
        else:
            expire = now + timedelta(minutes=self.settings.access_token_expire_minutes)
        
        to_encode.update({
            "exp": expire,
            "iat": now,
            "jti": str(uuid.uuid4())  # JWT ID
        })
        
        encoded_jwt = jwt.encode(
            to_encode,
            self.settings.secret_key,
            algorithm=self.settings.algorithm
        )
        
        return encoded_jwt
    
    def create_refresh_token(self, data: Dict[str, Any]) -> tuple[str, str]:
        """
        创建刷新令牌
        返回: (token, jti) 元组
        """
        to_encode = data.copy()
        now = datetime.utcnow()
        expire = now + timedelta(days=self.settings.refresh_token_expire_days)
        jti = str(uuid.uuid4())
        
        to_encode.update({
            "exp": expire,
            "iat": now,
            "jti": jti,
            "type": "refresh"
        })
        
        encoded_jwt = jwt.encode(
            to_encode,
            self.settings.secret_key,
            algorithm=self.settings.algorithm
        )
        
        return encoded_jwt, jti
    
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
    
    async def save_refresh_token(
        self, 
        db: AsyncSession, 
        user_id: str, 
        token: str, 
        jti: str,
        expires_at: datetime,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> RefreshToken:
        """保存 Refresh Token 到数据库"""
        try:
            refresh_token = RefreshToken(
                user_id=user_id,
                token=token,
                jti=jti,
                expires_at=expires_at,
                device_info=device_info,
                ip_address=ip_address
            )
            
            db.add(refresh_token)
            await db.commit()
            await db.refresh(refresh_token)
            
            logger.info(f"Refresh Token 已保存: user_id={user_id}, jti={jti}")
            return refresh_token
        
        except Exception as e:
            await db.rollback()
            logger.error(f"保存 Refresh Token 失败: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="保存令牌失败"
            )
    
    async def verify_refresh_token(self, db: AsyncSession, token: str) -> Dict[str, Any]:
        """验证 Refresh Token（从数据库检查）"""
        try:
            # 先验证 JWT 签名和过期时间
            payload = self.verify_token(token)
            
            # 检查 Token 类型
            if payload.get("type") != "refresh":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="无效的刷新令牌"
                )
            
            jti = payload.get("jti")
            
            # 从数据库查询 Token
            result = await db.execute(
                select(RefreshToken).where(
                    RefreshToken.jti == jti,
                    RefreshToken.is_revoked == False
                )
            )
            db_token = result.scalar_one_or_none()
            
            if not db_token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="刷新令牌不存在或已被撤销"
                )
            
            # 检查是否过期 - 统一使用 UTC 时间
            now = datetime.utcnow()
            # 确保 expires_at 是 naive datetime（移除时区信息）
            expires_at = db_token.expires_at.replace(tzinfo=None) if db_token.expires_at.tzinfo else db_token.expires_at
            
            if expires_at < now:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="刷新令牌已过期"
                )
            
            # 更新最后使用时间
            db_token.last_used_at = now
            await db.commit()
            
            return payload
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"验证 Refresh Token 失败: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的刷新令牌"
            )
    
    async def revoke_refresh_token(self, db: AsyncSession, jti: str):
        """撤销 Refresh Token"""
        try:
            result = await db.execute(
                select(RefreshToken).where(RefreshToken.jti == jti)
            )
            db_token = result.scalar_one_or_none()
            
            if db_token:
                db_token.is_revoked = True
                await db.commit()
                logger.info(f"Refresh Token 已撤销: jti={jti}")
        
        except Exception as e:
            await db.rollback()
            logger.error(f"撤销 Refresh Token 失败: {str(e)}")
    
    async def revoke_all_user_tokens(self, db: AsyncSession, user_id: str):
        """撤销用户的所有 Refresh Token"""
        try:
            result = await db.execute(
                select(RefreshToken).where(
                    RefreshToken.user_id == user_id,
                    RefreshToken.is_revoked == False
                )
            )
            tokens = result.scalars().all()
            
            for token in tokens:
                token.is_revoked = True
            
            await db.commit()
            logger.info(f"用户所有 Refresh Token 已撤销: user_id={user_id}, count={len(tokens)}")
        
        except Exception as e:
            await db.rollback()
            logger.error(f"撤销用户所有 Token 失败: {str(e)}")
    
    async def get_user_active_sessions(self, db: AsyncSession, user_id: str) -> list[RefreshToken]:
        """获取用户的活跃会话列表"""
        try:
            now = datetime.utcnow()
            result = await db.execute(
                select(RefreshToken).where(
                    RefreshToken.user_id == user_id,
                    RefreshToken.is_revoked == False
                ).order_by(RefreshToken.created_at.desc())
            )
            sessions = result.scalars().all()
            
            # 过滤未过期的会话（处理时区问题）
            active_sessions = []
            for session in sessions:
                expires_at = session.expires_at.replace(tzinfo=None) if session.expires_at.tzinfo else session.expires_at
                if expires_at > now:
                    active_sessions.append(session)
            
            return active_sessions
        
        except Exception as e:
            logger.error(f"获取用户活跃会话失败: {str(e)}")
            return []
    
    async def cleanup_expired_tokens(self, db: AsyncSession):
        """清理过期的 Refresh Token"""
        try:
            now = datetime.utcnow()
            result = await db.execute(
                select(RefreshToken)
            )
            all_tokens = result.scalars().all()
            
            # 手动过滤过期的 token（处理时区问题）
            expired_tokens = []
            for token in all_tokens:
                expires_at = token.expires_at.replace(tzinfo=None) if token.expires_at.tzinfo else token.expires_at
                if expires_at < now:
                    expired_tokens.append(token)
            
            for token in expired_tokens:
                await db.delete(token)
            
            await db.commit()
            logger.info(f"已清理 {len(expired_tokens)} 个过期的 Refresh Token")
        
        except Exception as e:
            await db.rollback()
            logger.error(f"清理过期 Token 失败: {str(e)}")


# 创建全局实例
auth_service = AuthService()

