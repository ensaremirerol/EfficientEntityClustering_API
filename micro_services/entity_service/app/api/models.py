from pydantic import BaseModel


class EntityIn(BaseModel):
    entity_id: str
    mention: str
    entity_source: str
    entity_source_id: str


class EntityOut(BaseModel):
    entity_id: str
    mention: str
    entity_source: str
    entity_source_id: str
    has_cluster: bool
    cluster_id: str
    has_mention_vector: bool
