import fitz  # PyMuPDF
from pathlib import Path
from typing import Dict, Any, List
import asyncio
from loguru import logger
from docx import Document as DocxDocument
from paddleocr import PaddleOCR
import io
from PIL import Image

from app.config import get_settings


class DocumentProcessor:
    """文档处理服务"""
    
    def __init__(self):
        self.settings = get_settings()
        self.chunk_size = self.settings.chunk_size
        self.chunk_overlap = self.settings.chunk_overlap
        # 初始化OCR（延迟加载）
        self._ocr = None
    
    @property
    def ocr(self):
        """延迟初始化OCR"""
        if self._ocr is None:
            self._ocr = PaddleOCR(use_angle_cls=True, lang='ch', show_log=False)
        return self._ocr
    
    async def process_document(self, file_path: Path) -> Dict[str, Any]:
        """
        处理文档并提取内容
        
        Args:
            file_path: 文档文件路径
            
        Returns:
            包含文本块、图像和元数据的字典
        """
        file_ext = file_path.suffix.lower()
        
        logger.info(f"开始处理文档: {file_path.name}, 类型: {file_ext}")
        
        if file_ext == '.pdf':
            return await self._process_pdf(file_path)
        elif file_ext in ['.docx', '.doc']:
            return await self._process_docx(file_path)
        else:
            raise ValueError(f"不支持的文件格式: {file_ext}")
    
    async def _process_pdf(self, file_path: Path) -> Dict[str, Any]:
        """处理PDF文件"""
        doc = fitz.open(file_path)
        text_chunks = []
        images = []
        page_count = len(doc)
        
        logger.info(f"PDF文档共 {page_count} 页")
        
        for page_num in range(page_count):
            page = doc[page_num]
            
            # 提取文本
            text = page.get_text()
            if text.strip():
                chunks = self._chunk_text(text)
                for idx, chunk in enumerate(chunks):
                    text_chunks.append({
                        "content": chunk,
                        "page": page_num + 1,
                        "chunk_index": idx,
                        "type": "text"
                    })
            
            # 提取图像
            image_list = page.get_images()
            for img_idx, img in enumerate(image_list):
                try:
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    
                    # OCR识别
                    ocr_text = await self._ocr_image(image_bytes)
                    
                    images.append({
                        "page": page_num + 1,
                        "image_index": img_idx,
                        "ocr_text": ocr_text,
                        "image_data": image_bytes
                    })
                except Exception as e:
                    logger.warning(f"提取图像失败 (页{page_num + 1}, 图{img_idx}): {e}")
        
        doc.close()
        
        logger.info(f"处理完成: {len(text_chunks)} 个文本块, {len(images)} 张图像")
        
        return {
            "text_chunks": text_chunks,
            "images": images,
            "page_count": page_count,
            "metadata": {
                "chunk_count": len(text_chunks),
                "image_count": len(images)
            }
        }
    
    async def _process_docx(self, file_path: Path) -> Dict[str, Any]:
        """处理DOCX文件"""
        doc = DocxDocument(file_path)
        text_chunks = []
        images = []
        
        # 提取文本
        full_text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
        chunks = self._chunk_text(full_text)
        
        for idx, chunk in enumerate(chunks):
            text_chunks.append({
                "content": chunk,
                "page": 1,  # DOCX没有页码概念
                "chunk_index": idx,
                "type": "text"
            })
        
        # 提取图像
        for rel in doc.part.rels.values():
            if "image" in rel.target_ref:
                try:
                    image_data = rel.target_part.blob
                    ocr_text = await self._ocr_image(image_data)
                    
                    images.append({
                        "page": 1,
                        "image_index": len(images),
                        "ocr_text": ocr_text,
                        "image_data": image_data
                    })
                except Exception as e:
                    logger.warning(f"提取DOCX图像失败: {e}")
        
        logger.info(f"处理完成: {len(text_chunks)} 个文本块, {len(images)} 张图像")
        
        return {
            "text_chunks": text_chunks,
            "images": images,
            "page_count": 1,
            "metadata": {
                "chunk_count": len(text_chunks),
                "image_count": len(images)
            }
        }
    
    def _chunk_text(self, text: str) -> List[str]:
        """文本分块"""
        if not text.strip():
            return []
        
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = start + self.chunk_size
            
            # 如果不是最后一块，尝试在句子边界分割
            if end < text_length:
                # 查找句号、问号、感叹号
                for sep in ['。', '！', '？', '.', '!', '?', '\n']:
                    pos = text.rfind(sep, start, end)
                    if pos != -1:
                        end = pos + 1
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # 移动到下一个位置，保留重叠
            start = end - self.chunk_overlap if end < text_length else text_length
        
        return chunks
    
    async def _ocr_image(self, image_bytes: bytes) -> str:
        """OCR识别图像"""
        try:
            # 在线程池中运行OCR（避免阻塞）
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._run_ocr,
                image_bytes
            )
            return result
        except Exception as e:
            logger.warning(f"OCR识别失败: {e}")
            return ""
    
    def _run_ocr(self, image_bytes: bytes) -> str:
        """执行OCR识别"""
        try:
            image = Image.open(io.BytesIO(image_bytes))
            result = self.ocr.ocr(image_bytes, cls=True)
            
            if result and result[0]:
                texts = [line[1][0] for line in result[0]]
                return " ".join(texts)
            return ""
        except Exception as e:
            logger.warning(f"OCR处理失败: {e}")
            return ""

