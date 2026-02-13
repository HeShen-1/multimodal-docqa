from fastapi import HTTPException, status


class DocumentNotFoundError(HTTPException):
    """文档不存在异常"""
    def __init__(self, document_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"文档不存在: {document_id}"
        )


class DocumentProcessingError(HTTPException):
    """文档处理失败异常"""
    def __init__(self, message: str):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文档处理失败: {message}"
        )


class UnsupportedFileTypeError(HTTPException):
    """不支持的文件类型异常"""
    def __init__(self, file_type: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型: {file_type}"
        )


class FileSizeExceededError(HTTPException):
    """文件大小超限异常"""
    def __init__(self, max_size: int):
        super().__init__(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件大小超过限制: {max_size} 字节"
        )


class QueryError(HTTPException):
    """查询失败异常"""
    def __init__(self, message: str):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询失败: {message}"
        )


class RetrievalError(HTTPException):
    """检索失败异常"""
    def __init__(self, message: str):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"检索失败: {message}"
        )


class OllamaConnectionError(HTTPException):
    """Ollama连接失败异常"""
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="无法连接到Ollama服务"
        )

