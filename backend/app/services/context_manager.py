"""
对话上下文管理器
"""
from typing import List, Dict, Any, Optional
from app.models.conversation import Message


class ContextManager:
    """对话上下文管理器"""

    def __init__(self, max_history: int = 10, max_tokens: int = 4000):
        """
        初始化上下文管理器
        
        Args:
            max_history: 保留的最大历史对话轮数
            max_tokens: 最大Token数量（粗略估计）
        """
        self.max_history = max_history
        self.max_tokens = max_tokens

    def build_context(
        self,
        messages: List[Message],
        system_prompt: str,
        current_question: str
    ) -> str:
        """
        构建完整的上下文Prompt
        
        Args:
            messages: 历史消息列表
            system_prompt: 系统提示
            current_question: 当前问题
            
        Returns:
            完整的Prompt字符串
        """
        # 获取最近的历史消息
        recent_messages = self._get_recent_messages(messages)
        
        # 压缩历史（如果需要）
        compressed_history = self._compress_if_needed(recent_messages)
        
        # 构建Prompt
        context_parts = [system_prompt]
        
        # 添加历史对话
        if compressed_history:
            context_parts.append("\n## 对话历史\n")
            for msg in compressed_history:
                role_name = "用户" if msg.role == "user" else "助手"
                context_parts.append(f"{role_name}: {msg.content}\n")
        
        # 添加当前问题
        context_parts.append(f"\n## 当前问题\n用户: {current_question}\n")
        context_parts.append("\n请基于以上对话历史回答当前问题。")
        
        return "".join(context_parts)

    def _get_recent_messages(self, messages: List[Message]) -> List[Message]:
        """
        获取最近的消息
        
        Args:
            messages: 所有消息列表
            
        Returns:
            最近的消息列表
        """
        # 只保留最近的N轮对话（每轮包含用户和助手各一条消息）
        if len(messages) <= self.max_history * 2:
            return messages
        
        return messages[-(self.max_history * 2):]

    def _compress_if_needed(self, messages: List[Message]) -> List[Message]:
        """
        如果超过Token限制，压缩历史消息
        
        Args:
            messages: 消息列表
            
        Returns:
            压缩后的消息列表
        """
        # 粗略估计Token数量（中文约1.5字符/token，英文约4字符/token）
        total_chars = sum(len(msg.content) for msg in messages)
        estimated_tokens = total_chars / 2  # 简化估计
        
        if estimated_tokens <= self.max_tokens:
            return messages
        
        # 如果超过限制，只保留最近的消息
        compressed = []
        current_tokens = 0
        
        for msg in reversed(messages):
            msg_tokens = len(msg.content) / 2
            if current_tokens + msg_tokens > self.max_tokens:
                break
            compressed.insert(0, msg)
            current_tokens += msg_tokens
        
        return compressed

    def extract_context_summary(self, messages: List[Message]) -> str:
        """
        提取对话摘要（用于压缩）
        
        Args:
            messages: 消息列表
            
        Returns:
            对话摘要
        """
        if not messages:
            return ""
        
        # 简单实现：提取关键信息
        summary_parts = []
        
        # 提取用户的主要问题
        user_questions = [msg.content for msg in messages if msg.role == "user"]
        if user_questions:
            summary_parts.append(f"用户主要询问了: {', '.join(user_questions[:3])}")
        
        # 提取助手的关键回答
        assistant_responses = [msg.content[:100] for msg in messages if msg.role == "assistant"]
        if assistant_responses:
            summary_parts.append(f"助手提供了相关回答")
        
        return "; ".join(summary_parts)

    def should_compress(self, messages: List[Message]) -> bool:
        """
        判断是否需要压缩历史
        
        Args:
            messages: 消息列表
            
        Returns:
            是否需要压缩
        """
        # 如果消息数量超过阈值
        if len(messages) > self.max_history * 2:
            return True
        
        # 如果Token数量超过阈值
        total_chars = sum(len(msg.content) for msg in messages)
        estimated_tokens = total_chars / 2
        
        return estimated_tokens > self.max_tokens

    def format_message_for_llm(self, messages: List[Message]) -> List[Dict[str, str]]:
        """
        将消息格式化为LLM API所需的格式
        
        Args:
            messages: 消息列表
            
        Returns:
            格式化后的消息列表
        """
        formatted = []
        
        for msg in messages:
            formatted.append({
                "role": msg.role,
                "content": msg.content
            })
        
        return formatted

