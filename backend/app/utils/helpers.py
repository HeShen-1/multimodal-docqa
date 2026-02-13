import uuid
from datetime import datetime
from typing import Any, Dict


def generate_uuid() -> str:
    """生成UUID"""
    return str(uuid.uuid4())


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f}{unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f}TB"


def calculate_total_pages(total: int, page_size: int) -> int:
    """计算总页数"""
    return (total + page_size - 1) // page_size


def build_pagination_response(items: list, total: int, page: int, page_size: int) -> Dict[str, Any]:
    """构建分页响应"""
    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": calculate_total_pages(total, page_size)
    }

