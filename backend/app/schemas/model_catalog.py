from pydantic import BaseModel, ConfigDict, Field


class ModelCatalogItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    value: str = Field(..., description="模型值")
    label: str = Field(..., description="模型展示名称")
    provider: str = Field(..., description="模型提供方")
    enabled: bool = Field(True, description="是否启用")
    is_default: bool = Field(..., alias="isDefault", description="是否默认模型")
    supports_chat: bool = Field(..., alias="supportsChat", description="是否支持对话")
    supports_analysis: bool = Field(..., alias="supportsAnalysis", description="是否支持分析")


class ModelCatalogPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    default_model: str = Field(..., alias="defaultModel", description="默认模型")
    models: list[ModelCatalogItem] = Field(default_factory=list, description="可选模型列表")
