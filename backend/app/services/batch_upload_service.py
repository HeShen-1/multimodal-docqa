from typing import List, Dict, Any
from pathlib import Path
from loguru import logger
import asyncio
from datetime import datetime

from app.celery_app import celery_app
from app.services.document_processor import DocumentProcessor
from app.services.embedding_service import EmbeddingService
from app.models.document import DocumentStatus
from app.utils.helpers import generate_uuid


# 批量上传状态存储（生产环境应使用 Redis）
batch_status_store = {}


class BatchUploadService:
    """批量上传服务"""
    
    def __init__(self):
        self.max_batch_size = 10
    
    def create_batch(self, file_count: int) -> str:
        """创建批次"""
        batch_id = generate_uuid()
        batch_status_store[batch_id] = {
            "batch_id": batch_id,
            "total_files": file_count,
            "completed": 0,
            "processing": file_count,
            "failed": 0,
            "progress": 0,
            "documents": [],
            "created_at": datetime.utcnow().isoformat()
        }
        return batch_id
    
    def get_batch_status(self, batch_id: str) -> Dict[str, Any]:
        """获取批次状态"""
        return batch_status_store.get(batch_id)
    
    def update_document_status(
        self, 
        batch_id: str, 
        document_id: str, 
        status: str,
        message: str = ""
    ):
        """更新文档状态"""
        if batch_id not in batch_status_store:
            return
        
        batch = batch_status_store[batch_id]
        
        # 查找文档
        doc_found = False
        for doc in batch["documents"]:
            if doc["document_id"] == document_id:
                doc["status"] = status
                doc["message"] = message
                doc_found = True
                break
        
        if not doc_found:
            batch["documents"].append({
                "document_id": document_id,
                "status": status,
                "message": message
            })
        
        # 更新统计
        completed = sum(1 for d in batch["documents"] if d["status"] == "completed")
        failed = sum(1 for d in batch["documents"] if d["status"] == "failed")
        processing = batch["total_files"] - completed - failed
        
        batch["completed"] = completed
        batch["failed"] = failed
        batch["processing"] = processing
        batch["progress"] = int((completed + failed) / batch["total_files"] * 100)
    
    async def process_batch(
        self,
        batch_id: str,
        files: List[Dict[str, Any]],
        user_id: str
    ) -> List[str]:
        """处理批量上传"""
        document_ids = []
        
        for file_info in files:
            document_id = generate_uuid()
            document_ids.append(document_id)
            
            # 更新状态为处理中
            self.update_document_status(
                batch_id, 
                document_id, 
                "processing",
                "正在处理..."
            )
            
            # 提交异步任务
            process_single_document.delay(
                batch_id=batch_id,
                document_id=document_id,
                file_path=file_info["file_path"],
                file_name=file_info["file_name"],
                file_size=file_info["file_size"],
                file_type=file_info["file_type"],
                user_id=user_id
            )
        
        return document_ids


@celery_app.task(bind=True, name="tasks.process_single_document")
def process_single_document(
    self,
    batch_id: str,
    document_id: str,
    file_path: str,
    file_name: str,
    file_size: int,
    file_type: str,
    user_id: str
):
    """处理单个文档（Celery 任务）"""
    try:
        logger.info(f"开始处理文档: {document_id} ({file_name})")
        
        # 创建事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # 处理文档
            processor = DocumentProcessor()
            result = loop.run_until_complete(
                processor.process_document(Path(file_path))
            )
            
            # 向量化
            embedding_service = EmbeddingService()
            loop.run_until_complete(
                embedding_service.add_text_chunks(
                    document_id=document_id,
                    chunks=result["text_chunks"]
                )
            )
            
            # 更新状态为完成
            batch_service = BatchUploadService()
            batch_service.update_document_status(
                batch_id,
                document_id,
                "completed",
                "处理完成"
            )
            
            logger.info(f"文档处理完成: {document_id}")
            
            return {
                "status": "success",
                "document_id": document_id,
                "chunk_count": result["metadata"]["chunk_count"],
                "image_count": result["metadata"]["image_count"]
            }
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"文档处理失败: {document_id}, 错误: {e}")
        
        # 更新状态为失败
        batch_service = BatchUploadService()
        batch_service.update_document_status(
            batch_id,
            document_id,
            "failed",
            str(e)
        )
        
        return {
            "status": "failed",
            "document_id": document_id,
            "error": str(e)
        }


# 创建全局实例
batch_upload_service = BatchUploadService()

