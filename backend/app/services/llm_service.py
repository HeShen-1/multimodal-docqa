import httpx
import requests
import aiohttp
import re
import json
import asyncio
from typing import Dict, List, Union, AsyncGenerator, Any
from loguru import logger

from app.config import Settings, get_settings
from app.prompts import THINKING_PROMPT, SIMPLE_QA_PROMPT
from app.utils.exceptions import OllamaConnectionError


class LLMService:
    """LLM调用服务"""
    
    def __init__(self, settings: Settings = None):
        self.settings = settings or get_settings()
        # 使用 requests 而不是 httpx.AsyncClient (Windows 兼容性问题)
        self.ollama_base_url = self.settings.ollama_base_url.rstrip('/api')
        self.model_name = self.settings.ollama_llm_model
        
        logger.info("LLMService初始化完成")
    
    async def generate_answer(
        self,
        query: str,
        context: List[Dict],
        stream: bool = False,
        enable_thinking: bool = True,
        temperature: float = 0.7
    ) -> Union[Dict, AsyncGenerator]:
        """
        生成答案
        
        Args:
            query: 用户问题
            context: 检索到的上下文
            stream: 是否流式输出
            enable_thinking: 是否启用推理链
            temperature: 生成温度
            
        Returns:
            答案字典或流式生成器
        """
        # 构建prompt
        prompt = self._build_prompt(query, context, enable_thinking)
        
        # 准备请求
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "top_p": 0.9,
                "num_predict": 1024
            }
        }
        
        try:
            if stream:
                return self._generate_stream(payload)
            else:
                return await self._generate_once(payload, enable_thinking)
        except httpx.ConnectError:
            logger.error("无法连接到Ollama服务")
            raise OllamaConnectionError()
    
    def _build_prompt(self, query: str, context: List[Dict], enable_thinking: bool = True) -> str:
        """构建提示词"""
        # 如果没有上下文，让模型自己判断（简化版）
        if not context or len(context) == 0:
            return f"""你是智能助手。用户问题：{query}

判断：如果是日常问候或通用知识，直接回答；如果需要特定文档，告知用户需要上传文档。

回答："""
        
        # 格式化上下文
        context_text = "\n\n".join([
            f"[来源: {ctx.get('metadata', {}).get('document_id', 'unknown')}, 第{ctx.get('metadata', {}).get('page', 1)}页]\n{ctx['content']}"
            for ctx in context
        ])
        
        # 选择模板
        template = THINKING_PROMPT if enable_thinking else SIMPLE_QA_PROMPT
        
        # 填充模板
        return template.format(
            context=context_text,
            question=query
        )
    
    async def _generate_once(self, payload: Dict, enable_thinking: bool = True) -> Dict:
        """一次性生成"""
        def _sync_request():
            url = f"{self.ollama_base_url}/api/generate"
            response = requests.post(url, json=payload, timeout=120)
            return response
        
        response = await asyncio.to_thread(_sync_request)
        
        if response.status_code != 200:
            logger.error(f"LLM生成失败: {response.text}")
            raise Exception("LLM生成失败")
        
        result = response.json()
        response_text = result.get("response", "")
        
        # 解析thinking chain
        if enable_thinking:
            parsed = self.parse_thinking_chain(response_text)
        else:
            parsed = {
                "thinking": [],
                "answer": response_text
            }
        
        return parsed
    
    async def _generate_stream(self, payload: Dict) -> AsyncGenerator:
        """流式生成（使用 aiohttp）"""
        url = f"{self.ollama_base_url}/api/generate"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"流式生成失败: {error_text}")
                        raise OllamaConnectionError()
                    
                    # 逐行读取流式响应
                    async for line in response.content:
                        if line:
                            try:
                                # 解码并解析 JSON
                                line_text = line.decode('utf-8').strip()
                                if line_text:
                                    data = json.loads(line_text)
                                    
                                    # 提取生成的文本片段
                                    if 'response' in data:
                                        token = data['response']
                                        if token:
                                            yield token
                                    
                                    # 检查是否完成
                                    if data.get('done', False):
                                        break
                                        
                            except json.JSONDecodeError as e:
                                logger.warning(f"解析流式响应失败: {e}, line: {line_text}")
                                continue
                            except Exception as e:
                                logger.error(f"处理流式响应时出错: {e}")
                                continue
                                
        except aiohttp.ClientError as e:
            logger.error(f"无法连接到Ollama服务: {e}")
            raise OllamaConnectionError()
        except Exception as e:
            logger.error(f"流式生成异常: {e}")
            raise OllamaConnectionError()
    
    async def generate_general_answer(
        self,
        query: str,
        temperature: float = 0.7,
        stream: bool = False
    ) -> Union[Dict, AsyncGenerator]:
        """
        通用对话模式（无文档上下文）
        
        Args:
            query: 用户问题
            temperature: 生成温度
            stream: 是否流式输出
            
        Returns:
            答案字典或流式生成器
        """
        # 简化 prompt，让模型更容易理解
        prompt = f"""你是一个智能助手。用户问题：{query}

请判断：
- 如果是日常问候、通用知识、技术问题，直接回答
- 如果需要查看特定文档才能回答，礼貌告知用户需要上传文档

回答："""
        
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "top_p": 0.9,
                "num_predict": 512
            }
        }
        
        try:
            if stream:
                # 返回流式生成器
                logger.info(f"发送通用对话流式请求，问题: {query}")
                return self._generate_stream(payload)
            else:
                # 非流式模式
                def _sync_request():
                    url = f"{self.ollama_base_url}/api/generate"
                    response = requests.post(url, json=payload, timeout=60)
                    return response
                
                logger.info(f"发送通用对话请求，问题: {query}")
                response = await asyncio.to_thread(_sync_request)
                
                if response.status_code != 200:
                    logger.error(f"LLM生成失败: {response.text}")
                    return {
                        "thinking": [],
                        "answer": "抱歉，我暂时无法回答您的问题。请先上传相关文档，或者稍后再试。"
                    }
                
                result = response.json()
                response_text = result.get("response", "").strip()
                
                # 打印完整响应用于调试
                logger.info(f"模型原始响应: {response_text[:200]}...")
                logger.info(f"完整响应长度: {len(response_text)}")
                
                if not response_text:
                    response_text = "抱歉，我暂时无法回答您的问题。请先上传相关文档，我可以基于文档内容为您提供更准确的答案。"
                
                logger.info(f"通用对话生成完成，返回长度: {len(response_text)}")
                
                return {
                    "thinking": [],
                    "answer": response_text
                }
            
        except Exception as e:
            logger.error(f"通用对话生成失败: {e}")
            if stream:
                # 流式模式下返回错误生成器
                async def error_generator():
                    yield "抱歉，我暂时无法回答您的问题。"
                return error_generator()
            else:
                return {
                    "thinking": [],
                    "answer": "抱歉，我暂时无法回答您的问题。请先上传相关文档，或者稍后再试。"
                }
    
    def parse_thinking_chain(self, response: str) -> Dict[str, Any]:
        """解析Thinking Chain"""
        # 提取thinking部分
        thinking_match = re.search(
            r'<thinking>(.*?)</thinking>', 
            response, 
            re.DOTALL
        )
        
        # 提取answer部分
        answer_match = re.search(
            r'<answer>(.*?)</answer>', 
            response, 
            re.DOTALL
        )
        
        # 解析thinking步骤
        thinking_steps = []
        if thinking_match:
            thinking_text = thinking_match.group(1)
            # 匹配步骤（支持中英文冒号）
            steps = re.findall(
                r'\d+\.\s*([^:：\n]+)[：:]\s*([^\n]+)', 
                thinking_text
            )
            thinking_steps = [
                {"step": step[0].strip(), "content": step[1].strip()}
                for step in steps
            ]
        
        # 提取答案
        answer = answer_match.group(1).strip() if answer_match else response
        
        return {
            "thinking": thinking_steps,
            "answer": answer
        }
    
    async def close(self):
        """关闭连接"""
        # 使用 requests 库，无需关闭连接
        pass

