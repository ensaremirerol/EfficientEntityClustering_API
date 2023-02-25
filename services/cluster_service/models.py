from pydantic import BaseModel


class ClusterIn(BaseModel):
    cluster_id: str
    cluster_name: str


class ClusterAddEntityIn(BaseModel):
    entity_ids: list[str]


class ClusterOut(BaseModel):
    cluster_id: str
    cluster_name: str
    entity_ids: list[str]
    cluster_vector: list[float]


class DeleteClustersIn(BaseModel):
    cluster_ids: list[str]
