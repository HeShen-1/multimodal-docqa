from typing import List, Optional

from fastapi import HTTPException, status


class DocumentNotFoundError(HTTPException):
    """文档不存在异常"""

    def __init__(self, document_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"文档不存在: {document_id}",
        )


class DocumentProcessingError(HTTPException):
    """文档处理失败异常"""

    def __init__(self, message: str):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文档处理失败: {message}",
        )


class UnsupportedFileTypeError(HTTPException):
    """不支持的文件类型异常"""

    def __init__(self, file_type: str, allowed_types: Optional[List[str]] = None):
        detail = f"不支持的文件类型: {file_type}"
        if allowed_types:
            detail = f"{detail}，仅支持: {', '.join(allowed_types)}"
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class FileSizeExceededError(HTTPException):
    """文件大小超限异常"""

    def __init__(self, max_size: int):
        super().__init__(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件大小超过限制: {max_size} 字节",
        )


class QueryError(HTTPException):
    """查询失败异常"""

    def __init__(self, message: str):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询失败: {message}",
        )


class RetrievalError(HTTPException):
    """检索失败异常"""

    def __init__(self, message: str):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"检索失败: {message}",
        )


class OllamaConnectionError(HTTPException):
    """Ollama 连接失败异常"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="无法连接到 Ollama 服务",
        )


class LLMProviderError(HTTPException):
    """LLM 服务异常"""

    def __init__(self, message: str, status_code: int = status.HTTP_503_SERVICE_UNAVAILABLE):
        super().__init__(status_code=status_code, detail=message)


class NotFoundException(HTTPException):
    """资源不存在异常"""

    def __init__(self, message: str = "资源不存在"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=message)


class ValidationException(HTTPException):
    """校验失败异常"""

    def __init__(self, message: str = "校验失败"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
