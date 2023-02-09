from typing import List
from fastapi import APIRouter, HTTPException, Header
from .models import *

from eec import EntityClustererBridge, BaseEntityRepository, BaseEntity, NotFoundException, AlreadyExistsException

entities_router = APIRouter()


def _entityIn_to_entity(entity_in: EntityIn) -> BaseEntity:
    return BaseEntity(
        entity_id=entity_in.entity_id,
        mention=entity_in.mention,
        entity_source=entity_in.entity_source,
        entity_source_id=entity_in.entity_source_id
    )


def _entity_to_entityOut(entity: BaseEntity) -> EntityOut:
    return EntityOut(
        entity_id=entity.entity_id,
        mention=entity.mention,
        entity_source=entity.entity_source,
        entity_source_id=entity.entity_source_id,
        in_cluster=entity.in_cluster,
        cluster_id=entity.cluster_id if entity.in_cluster else '',
        has_mention_vector=entity.has_mention_vector
    )


@entities_router.get("/", response_model=List[EntityOut])
async def get_all_entities():
    entity_repo = EntityClustererBridge().entity_repository
    _all_entites: list[BaseEntity] = entity_repo.get_all_entities()
    return [
        _entity_to_entityOut(entity)
        for entity in _all_entites
    ]


@entities_router.get("/{entity_id}", response_model=EntityOut)
async def get_entity_by_id(entity_id: str):
    entity_repo = EntityClustererBridge().entity_repository
    try:
        entity: BaseEntity = entity_repo.get_entity_by_id(entity_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return _entity_to_entityOut(entity)


@entities_router.get("/source/{entity_source}/{entity_source_id}", response_model=EntityOut)
async def get_entity_by_source_id(entity_source: str, entity_source_id: str):
    entity_repo = EntityClustererBridge().entity_repository
    try:
        entity: BaseEntity = entity_repo.get_entity_by_source_id(entity_source, entity_source_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return _entity_to_entityOut(entity)


@entities_router.get("/source/{entity_source}", response_model=List[EntityOut])
async def get_entities_by_source(entity_source: str):
    entity_repo = EntityClustererBridge().entity_repository
    try:
        entities: list[BaseEntity] = entity_repo.get_entities_by_source(entity_source)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return [
        _entity_to_entityOut(entity)
        for entity in entities
    ]


@entities_router.post("/create-entity", response_model=EntityOut, status_code=201)
async def create_entity(payload: EntityIn):
    entity_repo = EntityClustererBridge().entity_repository
    entity: BaseEntity = _entityIn_to_entity(payload)
    try:
        entity = entity_repo.add_entity(entity)
    except AlreadyExistsException as e:
        raise HTTPException(status_code=409, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return _entity_to_entityOut(entity)


@entities_router.post("/create-entities", response_model=List[EntityOut], status_code=201)
async def create_entities(payload: List[EntityIn]):
    entity_repo = EntityClustererBridge().entity_repository
    entities: list[BaseEntity] = [
        _entityIn_to_entity(entity)
        for entity in payload
    ]
    try:
        entities = entity_repo.add_entities(entities)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return [
        _entity_to_entityOut(entity)
        for entity in entities
    ]


@entities_router.post("/update-entity", response_model=EntityOut, status_code=200)
async def update_entity(payload: EntityIn):
    entity_repo = EntityClustererBridge().entity_repository
    entity: BaseEntity = _entityIn_to_entity(payload)
    try:
        org_entity = entity_repo.delete_entity(entity.entity_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if org_entity.in_cluster:
        cluster_repo = EntityClustererBridge().cluster_repository
        cluster_repo.remove_entity_from_cluster(org_entity.cluster_id, org_entity.entity_id)

    try:
        org_entity.entity_id = entity.entity_id
        org_entity.mention = entity.mention
        org_entity.entity_source = entity.entity_source
        org_entity.entity_source_id = entity.entity_source_id
        entity_repo.add_entity(org_entity)
        return _entity_to_entityOut(org_entity)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@entities_router.delete("/delete-entity/{entity_id}", status_code=200)
async def delete_entity(entity_id: str):
    entity_repo = EntityClustererBridge().entity_repository
    try:
        entity = entity_repo.get_entity_by_id(entity_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if entity.in_cluster:
        raise HTTPException(status_code=409, detail="Entity is in a cluster and cannot be deleted")

    try:
        entity_repo.delete_entity(entity_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
