from pydantic import BaseModel
import uuid


class SearchRequest(BaseModel):
    query: str
    mode: str = "hybrid"  # 'text', 'image', 'hybrid'
    limit: int = 20
    object_id: uuid.UUID | None = None
    ontology_node_id: uuid.UUID | None = None


class SearchResult(BaseModel):
    id: str
    score: float
    content_type: str  # 'document_chunk', 'reference_media'
    title: str | None = None
    snippet: str | None = None
    source_id: uuid.UUID | None = None
    metadata: dict = {}


class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int
    query: str
    mode: str


class CategorySuggestion(BaseModel):
    ontology_node_id: uuid.UUID
    ontology_node_name: str
    confidence: float
    reason: str | None = None
