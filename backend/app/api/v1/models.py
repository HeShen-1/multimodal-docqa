from datetime import datetime

from fastapi import APIRouter, Depends
from loguru import logger

from app.dependencies import get_current_user, get_llm_service
from app.models.response import ApiResponse
from app.schemas.model_catalog import ModelCatalogItem, ModelCatalogPayload
from app.services.llm_service import LLMService


router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=ApiResponse, summary="获取可选模型列表")
async def list_models(
    current_user: dict = Depends(get_current_user),
    llm_service: LLMService = Depends(get_llm_service),
):
    logger.info(f"获取可选模型列表: user_id={current_user.get('user_id')}")

    payload = ModelCatalogPayload(
        default_model=llm_service.get_default_model_name(),
        models=[ModelCatalogItem(**item) for item in llm_service.get_available_models()],
    )

    return ApiResponse(
        code=100000,
        message="获取可选模型列表成功",
        data=payload.model_dump(by_alias=True),
        timestamp=datetime.utcnow(),
    )
