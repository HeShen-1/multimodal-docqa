from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List
from uuid import UUID

from fastapi import HTTPException
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.conversation import MessageCreate, MessageResponse
from app.services.conversation_service import ConversationService
from app.services.resilience_service import CircuitBreakerOpenError, resilience_manager

if TYPE_CHECKING:
    from app.services.llm_service import LLMService
    from app.services.retrieval_service import RetrievalService


def _sse(payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _build_sources_data(retrieval_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    sources_data = []
    for result in retrieval_results:
        metadata = result.get("metadata", {})
        sources_data.append(
            {
                "document_name": metadata.get("document_id", "unknown"),
                "page": metadata.get("page", 1),
                "chunk_id": result.get("id"),
                "content": result.get("content", "")[:200],
                "score": 1.0 - result.get("distance", 0) if "distance" in result else None,
            }
        )
    return sources_data


def _parse_thinking_steps(llm_service: LLMService, thinking_text: str) -> List[Dict[str, str]]:
    if not thinking_text.strip():
        return []

    parsed = llm_service.parse_thinking_chain(f"<thinking>{thinking_text}</thinking>\n<answer></answer>")
    steps = parsed.get("thinking") or []
    if steps:
        return steps

    return [{"step": "思考过程", "content": thinking_text.strip()}]


def _has_document_scope(conversation: Any) -> bool:
    document_ids = getattr(conversation, "document_ids", None)
    return bool(document_ids)


def _build_grounded_no_answer_payload() -> Dict[str, Any]:
    answer = (
        "结论：当前未找到足够依据回答该问题。\n\n"
        "依据：本次检索没有命中可支撑回答的文档片段。\n\n"
        "引用来源：无。\n\n"
        "边界说明：为了避免编造答案，我不会直接给出结论。请尝试缩小问题范围、调整关键词，"
        "或确认相关文档已上传并完成处理。"
    )
    return {
        "answer": answer,
        "thinking": [
            {"step": "问题分析", "content": "当前问题受文档范围约束，需要先找到可引用的文档证据。"},
            {"step": "证据筛选", "content": "本次检索未命中相关文档片段，无法形成可验证结论。"},
            {"step": "边界判断", "content": "为降低幻觉风险，返回“未找到依据”的受限回答。"},
        ],
    }


class ConversationMessageService:
    @staticmethod
    async def send_message(
        conversation_id: UUID,
        data: MessageCreate,
        current_user: dict,
        db: AsyncSession,
        retrieval_service: RetrievalService,
        llm_service: LLMService,
    ) -> Dict[str, MessageResponse]:
        start_time = time.time()
        logger.info(f"收到对话消息: conversation_id={conversation_id}, content={data.content[:50]}...")

        degradation = resilience_manager.evaluate_degradation()
        flags = degradation.get("flags", {})
        logger.info(
            f"当前降级状态: level={flags.get('level')}, "
            f"basic_query_only={flags.get('basicQueryOnly')}, "
            f"thinking_enabled={flags.get('thinkingChainEnabled')}"
        )

        slot_acquired = resilience_manager.degradation.try_acquire_query_slot()
        if not slot_acquired:
            raise HTTPException(status_code=429, detail="系统繁忙，请稍后重试")

        try:
            user_message = await ConversationService.add_message(
                db=db,
                conversation_id=conversation_id,
                user_id=current_user["user_id"],
                role="user",
                content=data.content,
            )

            conversation = await ConversationService.get_conversation(
                db=db,
                conversation_id=conversation_id,
                user_id=current_user["user_id"],
            )

            top_k = getattr(data, "top_k", 5)
            top_k = min(top_k, flags.get("maxRetrievalTopK", top_k))

            retrieval_results = []
            if not flags.get("basicQueryOnly"):

                async def _retrieve():
                    return await retrieval_service.hybrid_search(
                        query=data.content,
                        top_k=top_k,
                        document_ids=conversation.document_ids if conversation.document_ids else None,
                    )

                retrieval_results = await resilience_manager.execute(
                    service_name="retrieval_service",
                    operation_name="conversation_hybrid_search",
                    operation=_retrieve,
                    timeout_seconds=60,
                    enable_retry=True,
                )

            logger.info(f"检索到 {len(retrieval_results)} 条相关内容")

            enable_thinking = getattr(data, "enable_thinking", True) and flags.get("thinkingChainEnabled", True)
            temperature = getattr(data, "temperature", 0.7)

            if len(retrieval_results) == 0:
                if _has_document_scope(conversation):
                    logger.info("未检索到相关文档，返回受限答案")
                    llm_result = _build_grounded_no_answer_payload()
                else:
                    logger.info("未检索到相关文档，切换为通用对话模式")
                    llm_result = await llm_service.generate_general_answer(
                        query=data.content,
                        temperature=temperature,
                        model=data.model,
                    )
                sources_data = []
            else:
                llm_result = await llm_service.generate_answer(
                    query=data.content,
                    context=retrieval_results,
                    stream=False,
                    enable_thinking=enable_thinking,
                    temperature=temperature,
                    model=data.model,
                )
                sources_data = _build_sources_data(retrieval_results)

            if flags.get("simplifiedResponse") and llm_result.get("answer"):
                original_answer = llm_result["answer"]
                if len(original_answer) > 500:
                    llm_result["answer"] = original_answer[:500] + "\n\n[系统降级中，返回简化内容]"

            processing_time = time.time() - start_time
            logger.info(f"消息处理完成，耗时: {processing_time:.2f}s")

            assistant_message = await ConversationService.add_message(
                db=db,
                conversation_id=conversation_id,
                user_id=current_user["user_id"],
                role="assistant",
                content=llm_result["answer"],
                thinking=llm_result.get("thinking") if enable_thinking else None,
                sources=sources_data,
            )

            return {
                "user_message": MessageResponse.model_validate(user_message),
                "assistant_message": MessageResponse.model_validate(assistant_message),
            }
        except CircuitBreakerOpenError as exc:
            logger.error(f"下游服务熔断: {exc}")
            raise HTTPException(status_code=503, detail="下游服务暂时不可用，请稍后再试") from exc
        finally:
            resilience_manager.degradation.release_query_slot()

    @staticmethod
    async def stream_message_events(
        conversation_id: UUID,
        data: MessageCreate,
        current_user: dict,
        db: AsyncSession,
        retrieval_service: RetrievalService,
        llm_service: LLMService,
    ) -> AsyncGenerator[str, None]:
        degradation = resilience_manager.evaluate_degradation()
        flags = degradation.get("flags", {})
        slot_acquired = False

        try:
            slot_acquired = resilience_manager.degradation.try_acquire_query_slot()
            if not slot_acquired:
                yield _sse({"type": "error", "content": "系统繁忙，请稍后重试"})
                return

            logger.info(f"流式对话: conversation_id={conversation_id}, content={data.content[:50]}...")
            yield _sse({"type": "status", "content": "请求已接收，正在准备上下文"})

            await ConversationService.add_message(
                db=db,
                conversation_id=conversation_id,
                user_id=current_user["user_id"],
                role="user",
                content=data.content,
            )

            conversation = await ConversationService.get_conversation(
                db=db,
                conversation_id=conversation_id,
                user_id=current_user["user_id"],
            )

            top_k = getattr(data, "top_k", 5)
            top_k = min(top_k, flags.get("maxRetrievalTopK", top_k))

            retrieval_results = []
            if not flags.get("basicQueryOnly"):

                async def _retrieve():
                    return await retrieval_service.hybrid_search(
                        query=data.content,
                        top_k=top_k,
                        document_ids=conversation.document_ids if conversation.document_ids else None,
                    )

                retrieval_results = await resilience_manager.execute(
                    service_name="retrieval_service",
                    operation_name="conversation_stream_hybrid_search",
                    operation=_retrieve,
                    timeout_seconds=60,
                    enable_retry=True,
                )

            yield _sse({"type": "status", "content": f"检索到 {len(retrieval_results)} 条相关内容"})

            enable_thinking = getattr(data, "enable_thinking", True) and flags.get("thinkingChainEnabled", True)
            temperature = getattr(data, "temperature", 0.7)
            sources_data = _build_sources_data(retrieval_results)
            for source in sources_data:
                yield _sse(
                    {
                        "type": "source",
                        "fileName": source["document_name"],
                        "page": source["page"],
                        "content": source["content"],
                    }
                )

            full_answer = ""
            thinking_data = []

            if len(retrieval_results) == 0:
                if _has_document_scope(conversation):
                    logger.info("流式查询：未检索到相关文档，返回受限答案")
                    grounded_payload = _build_grounded_no_answer_payload()
                    thinking_data = grounded_payload["thinking"] if enable_thinking else []
                    for step in thinking_data:
                        yield _sse({"type": "thinking", "step": step["step"], "content": step["content"]})
                    full_answer = grounded_payload["answer"]
                    yield _sse({"type": "answer", "content": full_answer})
                else:
                    logger.info("流式查询：未检索到相关文档，使用通用对话流式模式")
                    stream = await llm_service.generate_general_answer(
                        query=data.content,
                        temperature=temperature,
                        stream=True,
                        model=data.model,
                    )
                    async for token in stream:
                        full_answer += token
                        yield _sse({"type": "answer", "content": token})
            else:
                logger.info("流式查询：基于文档生成答案（流式模式）")
                stream = await llm_service.generate_answer(
                    query=data.content,
                    context=retrieval_results,
                    stream=True,
                    enable_thinking=enable_thinking,
                    temperature=temperature,
                    model=data.model,
                )

                if not enable_thinking:
                    async for token in stream:
                        full_answer += token
                        yield _sse({"type": "answer", "content": token})
                else:
                    open_thinking = "<thinking>"
                    close_thinking = "</thinking>"
                    open_answer = "<answer>"
                    close_answer = "</answer>"
                    buffer = ""
                    thinking_buffer = ""
                    mode = "await_tags"

                    async for token in stream:
                        buffer += token
                        while buffer:
                            if mode == "await_tags":
                                stripped = buffer.lstrip()
                                if stripped.startswith(open_thinking):
                                    buffer = stripped[len(open_thinking):]
                                    mode = "thinking"
                                    continue
                                if stripped.startswith(open_answer):
                                    buffer = stripped[len(open_answer):]
                                    mode = "answer"
                                    continue
                                if open_thinking in stripped:
                                    buffer = stripped.split(open_thinking, 1)[1]
                                    mode = "thinking"
                                    continue
                                if open_answer in stripped:
                                    buffer = stripped.split(open_answer, 1)[1]
                                    mode = "answer"
                                    continue
                                if any(tag.startswith(stripped) for tag in (open_thinking, open_answer)):
                                    break
                                if len(stripped) > 24:
                                    buffer = stripped
                                    mode = "answer"
                                    continue
                                break

                            if mode == "thinking":
                                if close_thinking in buffer:
                                    chunk, buffer = buffer.split(close_thinking, 1)
                                    thinking_buffer += chunk
                                    thinking_data = _parse_thinking_steps(llm_service, thinking_buffer)
                                    for step in thinking_data:
                                        yield _sse({"type": "thinking", "step": step["step"], "content": step["content"]})
                                    mode = "await_answer"
                                    continue

                                keep = len(close_thinking) - 1
                                if len(buffer) <= keep:
                                    break
                                thinking_buffer += buffer[:-keep]
                                buffer = buffer[-keep:]
                                break

                            if mode == "await_answer":
                                stripped = buffer.lstrip()
                                if stripped.startswith(open_answer):
                                    buffer = stripped[len(open_answer):]
                                    mode = "answer"
                                    continue
                                if open_answer in stripped:
                                    buffer = stripped.split(open_answer, 1)[1]
                                    mode = "answer"
                                    continue
                                if open_answer.startswith(stripped):
                                    break
                                if len(stripped) > 16:
                                    buffer = stripped
                                    mode = "answer"
                                    continue
                                break

                            if mode == "answer":
                                if close_answer in buffer:
                                    chunk, buffer = buffer.split(close_answer, 1)
                                    if chunk:
                                        full_answer += chunk
                                        yield _sse({"type": "answer", "content": chunk})
                                    mode = "done"
                                    buffer = ""
                                    break

                                keep = len(close_answer) - 1
                                if len(buffer) <= keep:
                                    break
                                chunk = buffer[:-keep]
                                buffer = buffer[-keep:]
                                if chunk:
                                    full_answer += chunk
                                    yield _sse({"type": "answer", "content": chunk})
                                break

                            buffer = ""
                            break

                    if mode == "thinking" and not thinking_data and (thinking_buffer + buffer).strip():
                        thinking_data = _parse_thinking_steps(llm_service, f"{thinking_buffer}{buffer}")
                        for step in thinking_data:
                            yield _sse({"type": "thinking", "step": step["step"], "content": step["content"]})
                    elif mode in {"await_tags", "await_answer", "answer"}:
                        tail = buffer.replace(close_answer, "")
                        if tail.strip():
                            full_answer += tail
                            yield _sse({"type": "answer", "content": tail})

            if not full_answer.strip():
                full_answer = "抱歉，我暂时无法生成有效回答，请稍后重试。"
                yield _sse({"type": "answer", "content": full_answer})

            await ConversationService.add_message(
                db=db,
                conversation_id=conversation_id,
                user_id=current_user["user_id"],
                role="assistant",
                content=full_answer,
                thinking=thinking_data if thinking_data else None,
                sources=sources_data,
            )

            yield _sse({"type": "done"})
        except Exception as exc:
            logger.error(f"流式查询失败: {exc}")
            yield _sse({"type": "error", "content": f"查询失败: {str(exc)}"})
        finally:
            if slot_acquired:
                resilience_manager.degradation.release_query_slot()
