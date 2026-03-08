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
        metadata = result.get("metadata", {}) or {}
        sources_data.append(
            {
                "document_name": metadata.get("document_name") or result.get("document_id") or metadata.get("document_id", "unknown"),
                "page": result.get("page_no") or metadata.get("page", 1),
                "chunk_id": result.get("chunk_id") or result.get("id"),
                "content": result.get("content", "")[:200],
                "score": result.get("score"),
                "rerank_score": result.get("rerank_score"),
                "source_type": result.get("source_type") or metadata.get("source_type", metadata.get("type", "text")),
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


def _resolve_model_name(llm_service: LLMService, requested_model: str | None) -> str:
    try:
        resolved = llm_service.resolve_model(requested_model)
        return getattr(resolved, "model_name", None) or requested_model or "unknown"
    except Exception:
        return requested_model or "unknown"


def _build_response_meta(
    llm_service: LLMService,
    requested_model: str | None,
    strategy: str,
    rewritten_query: str,
    diagnostics: Dict[str, Any],
    latency_ms: float,
    citation_count: int,
) -> Dict[str, Any]:
    return {
        "model_name": _resolve_model_name(llm_service, requested_model),
        "latency_ms": round(latency_ms, 2),
        "retrieved_chunks": int(diagnostics.get("retrieved_chunks", 0)),
        "citation_count": citation_count,
        "fallback_reason": diagnostics.get("fallback_reason"),
        "retrieval_strategy": strategy,
        "rewritten_query": rewritten_query,
        "top_score": diagnostics.get("top_score", 0.0),
        "evidence_coverage": diagnostics.get("evidence_coverage", 0.0),
        "rerank_applied": bool(diagnostics.get("rerank_applied", False)),
    }


def _default_retrieval_context(query: str) -> Dict[str, Any]:
    return {
        "strategy": "hybrid",
        "rewritten_query": query,
        "results": [],
        "diagnostics": {
            "retrieved_chunks": 0,
            "citation_count": 0,
            "fallback_reason": None,
            "top_score": 0.0,
            "evidence_coverage": 0.0,
            "rerank_applied": False,
        },
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
            retrieval_context = _default_retrieval_context(data.content)
            if not flags.get("basicQueryOnly"):

                async def _retrieve():
                    return await retrieval_service.retrieve_context(
                        query=data.content,
                        top_k=top_k,
                        document_ids=conversation.document_ids if conversation.document_ids else None,
                    )

                retrieval_context = await resilience_manager.execute(
                    service_name="retrieval_service",
                    operation_name="conversation_hybrid_search",
                    operation=_retrieve,
                    timeout_seconds=60,
                    enable_retry=True,
                )

            retrieval_results = retrieval_context["results"]
            logger.info(f"检索到 {len(retrieval_results)} 条相关内容")

            enable_thinking = getattr(data, "enable_thinking", True) and flags.get("thinkingChainEnabled", True)
            temperature = getattr(data, "temperature", 0.7)
            no_answer_decision = retrieval_service.should_ground_no_answer(
                retrieval_results,
                has_document_scope=_has_document_scope(conversation),
            )
            retrieval_context["diagnostics"]["fallback_reason"] = no_answer_decision["reason"]

            if no_answer_decision["should_ground"]:
                logger.info(f"检索证据不足，返回受限答案: reason={no_answer_decision['reason']}")
                llm_result = _build_grounded_no_answer_payload()
                sources_data = []
            elif len(retrieval_results) == 0:
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

            processing_time_ms = (time.time() - start_time) * 1000
            response_meta = _build_response_meta(
                llm_service=llm_service,
                requested_model=data.model,
                strategy=retrieval_context["strategy"],
                rewritten_query=retrieval_context["rewritten_query"],
                diagnostics=retrieval_context["diagnostics"],
                latency_ms=processing_time_ms,
                citation_count=len(sources_data),
            )
            logger.info(f"消息处理完成，耗时: {processing_time_ms:.2f}ms")

            assistant_message = await ConversationService.add_message(
                db=db,
                conversation_id=conversation_id,
                user_id=current_user["user_id"],
                role="assistant",
                content=llm_result["answer"],
                thinking=llm_result.get("thinking") if enable_thinking else None,
                sources=sources_data,
                extra_data=response_meta,
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
        start_time = time.time()

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
            retrieval_context = _default_retrieval_context(data.content)
            if not flags.get("basicQueryOnly"):

                async def _retrieve():
                    return await retrieval_service.retrieve_context(
                        query=data.content,
                        top_k=top_k,
                        document_ids=conversation.document_ids if conversation.document_ids else None,
                    )

                retrieval_context = await resilience_manager.execute(
                    service_name="retrieval_service",
                    operation_name="conversation_stream_hybrid_search",
                    operation=_retrieve,
                    timeout_seconds=60,
                    enable_retry=True,
                )

            retrieval_results = retrieval_context["results"]
            yield _sse({"type": "status", "content": f"检索到 {len(retrieval_results)} 条相关内容"})

            enable_thinking = getattr(data, "enable_thinking", True) and flags.get("thinkingChainEnabled", True)
            temperature = getattr(data, "temperature", 0.7)
            no_answer_decision = retrieval_service.should_ground_no_answer(
                retrieval_results,
                has_document_scope=_has_document_scope(conversation),
            )
            retrieval_context["diagnostics"]["fallback_reason"] = no_answer_decision["reason"]

            sources_data = _build_sources_data(retrieval_results) if not no_answer_decision["should_ground"] else []
            for source in sources_data:
                yield _sse(
                    {
                        "type": "source",
                        "fileName": source["document_name"],
                        "page": source["page"],
                        "content": source["content"],
                        "score": source["score"],
                        "rerank_score": source["rerank_score"],
                        "source_type": source["source_type"],
                    }
                )

            full_answer = ""
            thinking_data = []

            if no_answer_decision["should_ground"]:
                logger.info(f"流式查询：证据不足，返回受限答案: reason={no_answer_decision['reason']}")
                grounded_payload = _build_grounded_no_answer_payload()
                thinking_data = grounded_payload["thinking"] if enable_thinking else []
                for step in thinking_data:
                    yield _sse({"type": "thinking", "step": step["step"], "content": step["content"]})
                full_answer = grounded_payload["answer"]
                yield _sse({"type": "answer", "content": full_answer})
            elif len(retrieval_results) == 0:
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

            response_meta = _build_response_meta(
                llm_service=llm_service,
                requested_model=data.model,
                strategy=retrieval_context["strategy"],
                rewritten_query=retrieval_context["rewritten_query"],
                diagnostics=retrieval_context["diagnostics"],
                latency_ms=(time.time() - start_time) * 1000,
                citation_count=len(sources_data),
            )

            await ConversationService.add_message(
                db=db,
                conversation_id=conversation_id,
                user_id=current_user["user_id"],
                role="assistant",
                content=full_answer,
                thinking=thinking_data if thinking_data else None,
                sources=sources_data,
                extra_data=response_meta,
            )

            yield _sse({"type": "done", **response_meta})
        except Exception as exc:
            logger.error(f"流式查询失败: {exc}")
            yield _sse({"type": "error", "content": f"查询失败: {str(exc)}"})
        finally:
            if slot_acquired:
                resilience_manager.degradation.release_query_slot()
