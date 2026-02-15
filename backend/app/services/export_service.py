"""
对话导出服务
"""
from typing import List, Dict, Any
import json
from datetime import datetime
from io import BytesIO

from app.models.conversation import Conversation, Message


class ExportService:
    """对话导出服务"""

    @staticmethod
    def export_to_markdown(
        conversation: Conversation,
        messages: List[Message],
        include_thinking: bool = True,
        include_sources: bool = True
    ) -> str:
        """
        导出对话为Markdown格式
        
        Args:
            conversation: 对话对象
            messages: 消息列表
            include_thinking: 是否包含思考过程
            include_sources: 是否包含引用来源
            
        Returns:
            Markdown格式的字符串
        """
        lines = []
        
        # 标题和元信息
        lines.append(f"# {conversation.title}\n")
        lines.append(f"**创建时间**: {conversation.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append(f"**消息数量**: {conversation.message_count}\n")
        
        if conversation.document_ids:
            lines.append(f"**关联文档**: {', '.join(conversation.document_ids)}\n")
        
        lines.append("\n---\n\n")
        
        # 对话内容
        for i, msg in enumerate(messages, 1):
            role_name = "👤 用户" if msg.role == "user" else "🤖 助手"
            timestamp = msg.created_at.strftime('%H:%M:%S')
            
            lines.append(f"## {role_name} ({timestamp})\n\n")
            lines.append(f"{msg.content}\n\n")
            
            # 思考过程
            if include_thinking and msg.thinking and msg.role == "assistant":
                lines.append("### 💭 思考过程\n\n")
                if isinstance(msg.thinking, dict):
                    for key, value in msg.thinking.items():
                        lines.append(f"**{key}**: {value}\n\n")
                else:
                    lines.append(f"{msg.thinking}\n\n")
            
            # 引用来源
            if include_sources and msg.sources and msg.role == "assistant":
                lines.append("### 📚 引用来源\n\n")
                for j, source in enumerate(msg.sources, 1):
                    if isinstance(source, dict):
                        doc_name = source.get('document_name', '未知文档')
                        content = source.get('content', '')
                        score = source.get('score', 0)
                        lines.append(f"{j}. **{doc_name}** (相似度: {score:.2f})\n")
                        lines.append(f"   > {content[:200]}...\n\n")
                    else:
                        lines.append(f"{j}. {source}\n\n")
            
            lines.append("---\n\n")
        
        # 页脚
        lines.append(f"\n*导出时间: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC*\n")
        
        return "".join(lines)

    @staticmethod
    def export_to_json(
        conversation: Conversation,
        messages: List[Message],
        include_thinking: bool = True,
        include_sources: bool = True
    ) -> str:
        """
        导出对话为JSON格式
        
        Args:
            conversation: 对话对象
            messages: 消息列表
            include_thinking: 是否包含思考过程
            include_sources: 是否包含引用来源
            
        Returns:
            JSON格式的字符串
        """
        data = {
            "conversation": {
                "id": str(conversation.id),
                "title": conversation.title,
                "document_ids": conversation.document_ids,
                "message_count": conversation.message_count,
                "created_at": conversation.created_at.isoformat(),
                "updated_at": conversation.updated_at.isoformat()
            },
            "messages": []
        }
        
        for msg in messages:
            message_data = {
                "id": str(msg.id),
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat()
            }
            
            if include_thinking and msg.thinking:
                message_data["thinking"] = msg.thinking
            
            if include_sources and msg.sources:
                message_data["sources"] = msg.sources
            
            data["messages"].append(message_data)
        
        data["exported_at"] = datetime.utcnow().isoformat()
        
        return json.dumps(data, ensure_ascii=False, indent=2)

    @staticmethod
    def export_to_pdf(
        conversation: Conversation,
        messages: List[Message],
        include_thinking: bool = True,
        include_sources: bool = True
    ) -> bytes:
        """
        导出对话为PDF格式
        
        注意: 需要安装 reportlab 库
        这里提供一个简化实现，实际使用时可以根据需要优化
        
        Args:
            conversation: 对话对象
            messages: 消息列表
            include_thinking: 是否包含思考过程
            include_sources: 是否包含引用来源
            
        Returns:
            PDF文件的字节数据
        """
        try:
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
        except ImportError:
            # 如果没有安装reportlab，返回Markdown格式的字节数据
            markdown_content = ExportService.export_to_markdown(
                conversation, messages, include_thinking, include_sources
            )
            return markdown_content.encode('utf-8')
        
        # 创建PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        story = []
        styles = getSampleStyleSheet()
        
        # 标题
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30
        )
        story.append(Paragraph(conversation.title, title_style))
        story.append(Spacer(1, 0.2 * inch))
        
        # 元信息
        meta_info = f"创建时间: {conversation.created_at.strftime('%Y-%m-%d %H:%M:%S')}<br/>"
        meta_info += f"消息数量: {conversation.message_count}"
        story.append(Paragraph(meta_info, styles['Normal']))
        story.append(Spacer(1, 0.3 * inch))
        
        # 对话内容
        for msg in messages:
            role_name = "用户" if msg.role == "user" else "助手"
            timestamp = msg.created_at.strftime('%H:%M:%S')
            
            # 角色和时间
            role_text = f"<b>{role_name}</b> ({timestamp})"
            story.append(Paragraph(role_text, styles['Heading2']))
            
            # 消息内容
            story.append(Paragraph(msg.content, styles['Normal']))
            story.append(Spacer(1, 0.2 * inch))
        
        # 生成PDF
        doc.build(story)
        pdf_data = buffer.getvalue()
        buffer.close()
        
        return pdf_data

    @staticmethod
    def get_export_filename(conversation: Conversation, format: str) -> str:
        """
        生成导出文件名（仅ASCII字符）
        
        Args:
            conversation: 对话对象
            format: 导出格式
            
        Returns:
            文件名（仅ASCII字符）
        """
        # 使用对话ID作为文件名，避免中文字符编码问题
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        conversation_id = str(conversation.id)[:8]
        
        return f"conversation_{conversation_id}_{timestamp}.{format}"

