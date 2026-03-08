import re
import unicodedata
from pydantic import BaseModel, EmailStr, Field, validator, field_serializer
from typing import Optional
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo


def _normalize_identifier(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = re.sub(r"[\u200B\u200C\u200D\uFEFF]", "", normalized)
    return normalized.strip()


class UserRegister(BaseModel):
    """用户注册请求"""
    username: str = Field(..., min_length=3, max_length=20, description="用户名")
    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(..., min_length=8, max_length=32, description="密码")
    
    @validator('username')
    def validate_username(cls, v):
        v = _normalize_identifier(v)
        if len(v) < 3 or len(v) > 20:
            raise ValueError('用户名长度必须在3到20字符之间')
        if not re.fullmatch(r"[A-Za-z0-9_]+", v):
            raise ValueError('用户名只能包含字母、数字和下划线')
        return v

    @validator('email')
    def normalize_email(cls, v):
        return _normalize_identifier(str(v)).lower()
    
    @validator('password')
    def validate_password(cls, v):
        if not any(c.isalpha() for c in v):
            raise ValueError('密码必须包含字母')
        if not any(c.isdigit() for c in v):
            raise ValueError('密码必须包含数字')
        return v


class UserLogin(BaseModel):
    """用户登录请求"""
    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")

    @validator('username')
    def normalize_username(cls, v):
        v = _normalize_identifier(v)
        if not v:
            raise ValueError('用户名或邮箱不能为空')
        return v


class TokenResponse(BaseModel):
    """Token响应"""
    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(..., description="过期时间（秒）")


class RefreshTokenRequest(BaseModel):
    """刷新Token请求"""
    refresh_token: str = Field(..., description="刷新令牌")


class UserResponse(BaseModel):
    """用户信息响应"""
    id: UUID
    username: str
    email: str
    role: str
    avatar: Optional[str] = None
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
    
    @field_serializer('created_at', 'last_login_at')
    def serialize_datetime(self, dt: Optional[datetime], _info):
        """将UTC时间转换为北京时间"""
        if dt is None:
            return None
        if dt.tzinfo is None:
            # 如果是naive datetime，假设为UTC
            dt = dt.replace(tzinfo=ZoneInfo('UTC'))
        # 转换为北京时间
        beijing_time = dt.astimezone(ZoneInfo('Asia/Shanghai'))
        return beijing_time.strftime('%Y-%m-%d %H:%M:%S')


class UserProfile(BaseModel):
    """用户详细信息"""
    id: UUID
    username: str
    email: str
    role: str
    avatar: Optional[str] = None
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None
    document_count: int = 0
    query_count: int = 0
    storage_used: int = 0
    
    class Config:
        from_attributes = True
    
    @field_serializer('created_at', 'last_login_at')
    def serialize_datetime(self, dt: Optional[datetime], _info):
        """将UTC时间转换为北京时间"""
        if dt is None:
            return None
        if dt.tzinfo is None:
            # 如果是naive datetime，假设为UTC
            dt = dt.replace(tzinfo=ZoneInfo('UTC'))
        # 转换为北京时间
        beijing_time = dt.astimezone(ZoneInfo('Asia/Shanghai'))
        return beijing_time.strftime('%Y-%m-%d %H:%M:%S')

