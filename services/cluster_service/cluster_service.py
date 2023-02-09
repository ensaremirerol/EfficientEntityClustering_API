from typing import List
from fastapi import APIRouter, HTTPException, Header
from .models import *

from eec import EntityClustererBridge, BaseCluster, BaseEntity, NotFoundException, AlreadyExistsException, AlreadyInClusterException

cluster_router = APIRouter()


def _base_cluster_to_clusterOut(cluster: BaseCluster) -> ClusterOut:
    return ClusterOut(
        cluster_id=cluster.cluster_id,
        cluster_name=cluster.cluster_name,
        entity_ids=[entity.entity_id for entity in cluster.entities],
        cluster_vector=cluster.cluster_vector.tolist()
    )


@cluster_router.get("/", response_model=List[ClusterOut])
async def get_all_clusters():
    cluster_repo = EntityClustererBridge().cluster_repository
    _all_clusters: list[BaseCluster] = cluster_repo.get_all_clusters()
    return [
        _base_cluster_to_clusterOut(cluster)
        for cluster in _all_clusters
    ]


@cluster_router.get("/{cluster_id}", response_model=ClusterOut)
async def get_cluster_by_id(cluster_id: str):
    cluster_repo = EntityClustererBridge().cluster_repository
    try:
        cluster: BaseCluster = cluster_repo.get_cluster_by_id(cluster_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return _base_cluster_to_clusterOut(cluster)


@cluster_router.post("/", response_model=ClusterOut)
async def create_cluster(cluster_in: ClusterIn):
    cluster_repo = EntityClustererBridge().cluster_repository
    cluster = BaseCluster(
        cluster_id=cluster_in.cluster_id,
        cluster_name=cluster_in.cluster_name,
        entities=[]
    )
    try:
        cluster = cluster_repo.add_cluster(cluster)

    except AlreadyExistsException as e:
        raise HTTPException(status_code=409, detail=e.message)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return _base_cluster_to_clusterOut(cluster)


@cluster_router.delete("/{cluster_id}")
async def delete_cluster(cluster_id: str):
    cluster_repo = EntityClustererBridge().cluster_repository
    try:
        cluster_repo.delete_cluster(cluster_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return


@cluster_router.delete("/")
async def delete_all_clusters():
    cluster_repo = EntityClustererBridge().cluster_repository
    try:
        cluster_repo.delete_all_clusters()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return


@cluster_router.post("/{cluster_id}/add-entity", response_model=ClusterOut)
async def add_entity_to_cluster(cluster_id: str, entity_id: str):
    cluster_repo = EntityClustererBridge().cluster_repository
    try:
        cluster_repo.add_entity_to_cluster(cluster_id=cluster_id, entity_id=entity_id)
    except AlreadyExistsException as e:
        raise HTTPException(status_code=409, detail=e.message)
    except AlreadyInClusterException as e:
        raise HTTPException(status_code=409, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    cluster = cluster_repo.get_cluster_by_id(cluster_id)
    return _base_cluster_to_clusterOut(cluster)


@cluster_router.post("/{cluster_id}/add-entities", response_model=ClusterOut)
async def add_entities_to_cluster(cluster_id: str, payload: ClusterAddEntityIn):
    cluster_repo = EntityClustererBridge().cluster_repository
    try:
        for entity in payload.entity_ids:
            cluster_repo.add_entity_to_cluster(cluster_id=cluster_id, entity_id=entity)
    except AlreadyExistsException as e:
        raise HTTPException(status_code=409, detail=e.message)
    except AlreadyInClusterException as e:
        raise HTTPException(status_code=409, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    cluster = cluster_repo.get_cluster_by_id(cluster_id)
    return _base_cluster_to_clusterOut(cluster)
