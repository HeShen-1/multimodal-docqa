from chromadb.telemetry.product import ProductTelemetryClient, ProductTelemetryEvent
from overrides import override


class NoOpProductTelemetryClient(ProductTelemetryClient):
    """禁用 ChromaDB 遥测上报。"""

    @override
    def capture(self, event: ProductTelemetryEvent) -> None:
        return None
