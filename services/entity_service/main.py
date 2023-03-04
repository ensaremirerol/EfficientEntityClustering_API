from models import DeleteEntitiesIn, EntityIn, EntityOut

from fastapi import FastAPI, Depends, HTTPException, status, Request, Security
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm, SecurityScopes
from fastapi.responses import FileResponse
from file_locker_middleware import FileLockerMiddleware
from eec.core.abstract.entity_repository import IEntityRepository
from eec import BaseEntityRepository, Neo4JEntityRepository, Neo4JHelper, EntityModel, NotFoundException, AlreadyExistsException
from dotenv import load_dotenv
from pathlib import Path
import os
import json
import logging
from gensim.models import KeyedVectors
import pandas as pd
import httpx

load_dotenv()

DATA_PATH = Path(os.getenv("DATA_PATH") or "data")
LOGGER_PATH = Path(os.getenv("LOGGER_PATH") or "logs")
SYSTEM_TYPE = os.getenv("SYSTEM_TYPE") or "base"
WORD2VEC_FILE = Path(os.getenv("WORD2VEC_FILE") or "/data/word2vec.model")

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL") or "http://eec.localhost/api/v1/auth"

entity_repository: IEntityRepository = None
last_entity_repository_update: float = None
o_auth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login", scopes={"admin": "Admin access"})


def get_word2vec_model():
    global WORD2VEC_FILE
    return KeyedVectors.load(str(WORD2VEC_FILE))


def neo4j_entity_repository():
    global entity_repository

    NEO4J_URI = os.getenv("NEO4J_URI")
    NEO4J_USER = os.getenv("NEO4J_USER")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

    Neo4JHelper(
        uri=NEO4J_URI,
        user=NEO4J_USER,
        password=NEO4J_PASSWORD
    )

    entity_repository = Neo4JEntityRepository(
        keyed_vectors=get_word2vec_model()
    )


def read_base_entity_repository():
    global entity_repository, last_entity_repository_update, DATA_PATH
    ENTITY_DATA_PATH = DATA_PATH / "entity_repository.json"

    if entity_repository is None or last_entity_repository_update is None or last_entity_repository_update < ENTITY_DATA_PATH.stat().st_mtime:
        if not ENTITY_DATA_PATH.exists():
            print("Entity repository not found. Creating new one.")
            entity_repository = BaseEntityRepository(
                entities=[],
                last_id=0,
                keyed_vectors=get_word2vec_model()
            )
            return
        with open(ENTITY_DATA_PATH, "r") as f:
            entity_repository = BaseEntityRepository.decode(
                json.load(f), keyed_vectors=get_word2vec_model())
        last_entity_repository_update = ENTITY_DATA_PATH.stat().st_mtime


def write_base_entity_repository():
    global entity_repository, last_entity_repository_update, DATA_PATH
    ENTITY_DATA_PATH = DATA_PATH / "entity_repository.json"

    temp_path = ENTITY_DATA_PATH.parent / (ENTITY_DATA_PATH.name + ".tmp")
    with open(temp_path, "w") as f:
        json.dump(entity_repository.encode(), f)
    os.replace(temp_path, ENTITY_DATA_PATH)
    last_entity_repository_update = ENTITY_DATA_PATH.stat().st_mtime


def _entityIn_to_entity(entity_in: EntityIn) -> EntityModel:
    return EntityModel(
        entity_id=entity_in.entity_id,
        mention=entity_in.mention,
        entity_source=entity_in.entity_source,
        entity_source_id=entity_in.entity_source_id
    )


def _entity_to_entityOut(entity: EntityModel) -> EntityOut:
    return EntityOut(
        entity_id=entity.entity_id,
        mention=entity.mention,
        entity_source=entity.entity_source,
        entity_source_id=entity.entity_source_id,
        has_cluster=entity.has_cluster,
        cluster_id=entity.cluster_id if entity.has_cluster else '',
        has_mention_vector=entity.has_mention_vector,
    )


app = FastAPI(
    title="Entity Repository",
    description="A service for managing entities.",
    version="1.0.0",
    root_path="/api/v1/entity_repository",
    root_path_in_servers=True
)

if SYSTEM_TYPE == "base":
    app.add_middleware(FileLockerMiddleware,
                       files_to_lock=[DATA_PATH / "entity_repository.json"],
                       before=read_base_entity_repository, after=write_base_entity_repository)


@app.on_event("startup")
async def startup_event():
    if SYSTEM_TYPE == "neo4j":
        neo4j_entity_repository()

    elif SYSTEM_TYPE == "base":
        read_base_entity_repository()


async def auth_required(security_scopes: SecurityScopes, token: dict = Depends(o_auth2_scheme)):
    response = httpx.get(
        f'{AUTH_SERVICE_URL}/verify',
        headers={'Authorization': f"Bearer {token}"}
    )
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if len(security_scopes.scopes) > 0 and security_scopes.scopes[0] not in response.json()["role"]:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return response.json()


@app.get("/entity/", response_model=list[EntityOut])
async def get_entities(
    user: dict = Security(auth_required, scopes=[])
):
    _all_entites: list[EntityModel] = entity_repository.get_all_entities()
    return [_entity_to_entityOut(entity) for entity in _all_entites]


@app.get("/entity/{entity_id}", response_model=EntityOut)
async def get_entity(entity_id: str, user: dict = Security(auth_required, scopes=[])):
    try:
        entity: EntityModel = entity_repository.get_entity_by_id(entity_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return _entity_to_entityOut(entity)


@app.get("/entity/source/{entity_source}", response_model=list[EntityOut])
async def get_entities_by_source(entity_source: str, user: dict = Security(auth_required, scopes=[])):
    try:
        entities: list[EntityModel] = entity_repository.get_entities_by_source(entity_source)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return [
        _entity_to_entityOut(entity)
        for entity in entities
    ]


@app.get("/entity/source/{entity_source}/{entity_source_id}", response_model=EntityOut)
async def get_entity_by_source_id(entity_source: str, entity_source_id: str, user: dict = Security(auth_required, scopes=[])):
    try:
        entity: EntityModel = entity_repository.get_entity_by_source_id(
            entity_source, entity_source_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return _entity_to_entityOut(entity)


@app.get("/next-entity", response_model=EntityOut)
async def get_next_entity(user: dict = Security(auth_required, scopes=[])):
    try:
        entity: EntityModel = entity_repository.get_random_unlabeled_entity()
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return _entity_to_entityOut(entity)


@app.get("/next-entity", response_model=EntityOut)
async def get_next_entity(num: int = 1, user: dict = Security(auth_required, scopes=[])):
    try:
        entities: list[EntityModel] = entity_repository.get_random_unlabeled_entities(num)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return [
        _entity_to_entityOut(entity)
        for entity in entities
    ]


@app.post("/entity/create", response_model=EntityOut, status_code=201)
async def create_entity(entity_in: EntityIn, user: dict = Security(auth_required, scopes=["admin"])):
    entity: EntityModel = _entityIn_to_entity(entity_in)
    try:
        entity = entity_repository.add_entity(entity)
    except AlreadyExistsException as e:
        raise HTTPException(status_code=409, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return _entity_to_entityOut(entity)


@app.post("/entities/create", response_model=list[EntityOut], status_code=201)
async def create_entities(entities_in: list[EntityIn], user: dict = Security(auth_required, scopes=["admin"])):
    entities: list[EntityModel] = [
        _entityIn_to_entity(entity)
        for entity in entities_in
    ]
    try:
        entities = entity_repository.add_entities(entities, suppress_exceptions=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return [
        _entity_to_entityOut(entity)
        for entity in entities
    ]


@app.post("/entity/{entity_id}/update", response_model=EntityOut, status_code=200)
async def update_entity(entity_id: str, entity_in: EntityIn, user: dict = Security(auth_required, scopes=["admin"])):
    entity: EntityModel = _entityIn_to_entity(entity_in)
    try:
        org_entity = entity_repository.get_entity_by_id(entity_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if org_entity.has_cluster:
        # TODO: adapt update to cluster
        raise HTTPException(status_code=409, detail="Entity is in cluster and cannot be updated")

    try:
        entity = entity_repository.update_entity(entity)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return _entity_to_entityOut(entity)


@app.delete("/entity/{entity_id}/delete", status_code=204)
async def delete_entity(entity_id: str, user: dict = Security(auth_required, scopes=["admin"])):
    try:
        entity = entity_repository.get_entity_by_id(entity_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if entity.has_cluster:
        raise HTTPException(status_code=409, detail="Entity is in a cluster and cannot be deleted")

    try:
        entity_repository.delete_entity(entity_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/entities/delete", status_code=204)
async def delete_entities(payload: DeleteEntitiesIn, user: dict = Security(auth_required, scopes=["admin"])):
    try:
        entity_repository.delete_entities(payload.entity_ids, suppress_exceptions=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/export/csv", response_class=FileResponse)
async def export_entities_csv(user: dict = Security(auth_required, scopes=["admin"])):
    _all_entites: list[EntityModel] = entity_repository.get_all_entities()
    pd.DataFrame([
        {
            'entity_id': entity.entity_id,
            'mention': entity.mention,
            'entity_source': entity.entity_source,
            'entity_source_id': entity.entity_source_id,
            'in_cluster': entity.has_cluster,
            'cluster_id': entity.cluster_id if entity.has_cluster else '',
            'has_mention_vector': entity.has_mention_vector,
            'mention_vector': entity.mention_vector if entity.has_mention_vector else ''
        }
        for entity in _all_entites
    ]).to_csv(
        './tmp/entities.csv',
    )

    return FileResponse(
        path="./tmp/entities.csv",
        filename="entities.csv",
        media_type="text/csv"
    )


if __name__ == "__main__":
    print("only debug")
    logging.basicConfig(level=logging.DEBUG)
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="debug")
