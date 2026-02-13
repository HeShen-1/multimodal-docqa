from fastapi import APIRouter, Depends, Query
from typing import Optional
import time
from loguru import logger

from app.models.query import QueryRequest, QueryResponse, QueryHistoryResponse
from app.models.response import ApiResponse
from app.services.retrieval_service import RetrievalService
from app.services.llm_service import LLMService
from app.dependencies import get_retrieval_service, get_llm_service
from app.utils.helpers import build_pagination_response, generate_uuid

router = APIRouter(prefix="/query", tags=["query"])

# 临时存储查询历史（生产环境应使用数据库）
query_history_db = []


@router.post("", response_model=ApiResponse)
async def query_documents(
    request: QueryRequest,
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
    llm_service: LLMService = Depends(get_llm_service)
):
    """执行问答"""
    start_time = time.time()
    
    logger.info(f"收到查询: {request.question}")
    
    # 检索相关文档
    retrieval_results = await retrieval_service.hybrid_search(
        query=request.question,
        top_k=request.top_k,
        document_ids=request.document_ids if request.document_ids else None
    )
    
    logger.info(f"检索到 {len(retrieval_results)} 条相关内容")
    
    # 如果没有检索到任何内容，切换为通用对话模式
    if len(retrieval_results) == 0:
        logger.info("未检索到相关文档，切换为通用对话模式")
        llm_result = await llm_service.generate_general_answer(
            query=request.question,
            temperature=request.temperature
        )
    else:
        # 生成基于文档的答案
        llm_result = await llm_service.generate_answer(
            query=request.question,
            context=retrieval_results,
            stream=False,
            enable_thinking=request.enable_thinking,
            temperature=request.temperature
        )
    
    processing_time = time.time() - start_time
    
    # 格式化来源
    sources = []
    for result in retrieval_results:
        metadata = result.get('metadata', {})
        sources.append({
            "fileName": metadata.get('document_id', 'unknown'),
            "page": metadata.get('page', 1),
            "chunkId": result.get('id'),
            "content": result.get('content', '')[:200],  # 截取前200字符
            "relevanceScore": 1.0 - result.get('distance', 0) if 'distance' in result else None
        })
    
    # 构建响应
    response_data = {
        "answer": llm_result["answer"],
        "thinking": llm_result.get("thinking", []) if request.enable_thinking else None,
        "sources": sources,
        "processingTime": round(processing_time, 2),
        "retrievalStats": {
            "vectorResults": len(retrieval_results),
            "bm25Results": 0,
            "imageResults": 0,
            "fusedResults": len(retrieval_results)
        }
    }
    
    # 保存历史记录
    history_item = {
        "id": generate_uuid(),
        "question": request.question,
        "answer": llm_result["answer"],
        "documentIds": request.document_ids,
        "processingTime": round(processing_time, 2),
        "createdAt": time.time()
    }
    query_history_db.append(history_item)
    
    logger.info(f"查询完成，耗时: {processing_time:.2f}s")
    
    return ApiResponse(
        code=100000,
        message="success",
        data=response_data
    )


@router.post("/stream")
async def query_documents_stream(
    request: QueryRequest,
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
    llm_service: LLMService = Depends(get_llm_service)
):
    """流式问答"""
    from fastapi.responses import StreamingResponse
    import json
    
    async def generate():
        try:
            # 检索相关文档
            retrieval_results = await retrieval_service.hybrid_search(
                query=request.question,
                top_k=request.top_k,
                document_ids=request.document_ids if request.document_ids else None
            )
            
            # 发送检索状态
            yield f"data: {json.dumps({'type': 'status', 'content': f'检索到{len(retrieval_results)}条相关内容'}, ensure_ascii=False)}\n\n"
            
            # 判断是否有文档
            if len(retrieval_results) == 0:
                # 无文档，使用通用对话模式（流式）
                logger.info("流式查询：未检索到相关文档，使用通用对话流式模式")
                stream = await llm_service.generate_general_answer(
                    query=request.question,
                    temperature=request.temperature,
                    stream=True
                )
                
                # 逐字发送答案
                async for token in stream:
                    yield f"data: {json.dumps({'type': 'answer', 'content': token}, ensure_ascii=False)}\n\n"
                    
            else:
                # 有文档，生成基于文档的答案（流式）
                logger.info("流式查询：基于文档生成答案（流式模式）")
                
                # 如果启用thinking，先发送thinking步骤（非流式）
                if request.enable_thinking:
                    # 先生成一次非流式的来获取thinking
                    temp_result = await llm_service.generate_answer(
                        query=request.question,
                        context=retrieval_results,
                        stream=False,
                        enable_thinking=True,
                        temperature=request.temperature
                    )
                    
                    # 发送thinking步骤
                    if temp_result.get('thinking'):
                        for step in temp_result['thinking']:
                            yield f"data: {json.dumps({'type': 'thinking', 'step': step['step'], 'content': step['content']}, ensure_ascii=False)}\n\n"
                    
                    # 发送答案（已经生成好了）
                    yield f"data: {json.dumps({'type': 'answer', 'content': temp_result['answer']}, ensure_ascii=False)}\n\n"
                else:
                    # 不需要thinking，直接流式生成
                    stream = await llm_service.generate_answer(
                        query=request.question,
                        context=retrieval_results,
                        stream=True,
                        enable_thinking=False,
                        temperature=request.temperature
                    )
                    
                    # 逐字发送答案
                    async for token in stream:
                        yield f"data: {json.dumps({'type': 'answer', 'content': token}, ensure_ascii=False)}\n\n"
                
                # 发送来源
                for result_item in retrieval_results:
                    metadata = result_item.get('metadata', {})
                    source_data = {
                        "type": "source",
                        "fileName": metadata.get('document_id', 'unknown'),
                        "page": metadata.get('page', 1),
                        "content": result_item.get('content', '')[:100]
                    }
                    yield f"data: {json.dumps(source_data, ensure_ascii=False)}\n\n"
            
            # 发送完成信号
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            logger.error(f"流式查询失败: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': f'查询失败: {str(e)}'}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/history", response_model=ApiResponse)
async def get_query_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    start_date: Optional[str] = Query(None, alias="startDate"),
    end_date: Optional[str] = Query(None, alias="endDate")
):
    """获取查询历史"""
    # 排序（最新的在前）
    sorted_history = sorted(query_history_db, key=lambda x: x["createdAt"], reverse=True)
    
    # 分页
    total = len(sorted_history)
    start = (page - 1) * page_size
    end = start + page_size
    items = sorted_history[start:end]
    
    return ApiResponse(
        code=100000,
        message="success",
        data=build_pagination_response(items, total, page, page_size)
    )

