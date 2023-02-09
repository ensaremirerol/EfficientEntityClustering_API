from pydantic import BaseModel

class MentionOut(BaseModel):
    entity_id: str
    mention: str
    entity_source: str
    entity_source_id: str
    possible_cluster_ids: list[str]
    possible_cluster_names: list[str]
    