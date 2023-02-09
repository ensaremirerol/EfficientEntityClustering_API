from typing import List
from fastapi import APIRouter, HTTPException, Header
from .models import *

from eec import EntityClustererBridge, BaseEntityRepository, BaseEntity, NotFoundException, AlreadyExistsException

mention_clustering_router = APIRouter()


@mention_clustering_router.get("/", response_model=MentionOut)
async def get_prediction_for_next_mention():
    entity_repo = EntityClustererBridge().entity_repository
    method = EntityClustererBridge().mention_clustering_method
    entity: BaseEntity = entity_repo.get_random_unlabeled_entity()

    possible_clusters = method.getPossibleClusters(entity)

    return MentionOut(
        entity_id=entity.entity_id,
        mention=entity.mention,
        entity_source=entity.entity_source,
        entity_source_id=entity.entity_source_id,
        possible_cluster_ids=[cluster.cluster_id for cluster in possible_clusters],
        possible_cluster_names=[cluster.cluster_name for cluster in possible_clusters]
    )
