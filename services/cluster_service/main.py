from models import ClusterAddEntityIn, ClusterIn, \
    ClusterOut, DeleteClustersIn

from fastapi import FastAPI, Depends, HTTPException,\
    status, Request, Security
from fastapi.security import OAuth2PasswordBearer,\
    OAuth2PasswordRequestForm, SecurityScopes
from fastapi.responses import FileResponse
from file_locker_middleware import FileLockerMiddleware
from eec.core.abstract.entity_repository import IEntityRepository
from eec.core.abstract.cluster_repository import IClusterRepository
from eec import BaseEntityRepository, Neo4JEntityRepository,\
    BaseClusterRepository, Neo4JClusterRepository, Neo4JHelper,\
    EntityModel, ClusterModel, NotFoundException, AlreadyExistsException, AlreadyInClusterException
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
cluster_repository: IClusterRepository = None
last_entity_repository_update: float = None
last_cluster_repository_update: float = None
o_auth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login", scopes={"admin": "Admin access"})


def get_word2vec_model():
    global WORD2VEC_FILE
    return KeyedVectors.load(str(WORD2VEC_FILE))


def neo4j_repositories():
    global entity_repository, cluster_repository

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
    cluster_repository = Neo4JClusterRepository(
        entity_repository=entity_repository
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


def read_base_cluster_repository():
    global cluster_repository, entity_repository, last_cluster_repository_update, DATA_PATH
    CLUSTER_DATA_PATH = DATA_PATH / "cluster_repository.json"

    if cluster_repository is None or last_cluster_repository_update is None or last_cluster_repository_update < CLUSTER_DATA_PATH.stat().st_mtime:
        if not CLUSTER_DATA_PATH.exists():
            print("Cluster repository not found. Creating new one.")
            cluster_repository = BaseClusterRepository(
                entity_repository=entity_repository,
                clusters=[],
                last_cluster_id=0
            )
            return
        with open(CLUSTER_DATA_PATH, "r") as f:
            cluster_repository = BaseClusterRepository.decode(
                entity_repository=entity_repository,
                cluster_repository_dict=json.load(f)
            )
        last_cluster_repository_update = CLUSTER_DATA_PATH.stat().st_mtime


def write_base_cluster_repository():
    global cluster_repository, last_cluster_repository_update, DATA_PATH
    CLUSTER_DATA_PATH = DATA_PATH / "cluster_repository.json"

    temp_path = CLUSTER_DATA_PATH.parent / (CLUSTER_DATA_PATH.name + ".tmp")
    with open(temp_path, "w") as f:
        json.dump(cluster_repository.encode(), f)
    os.replace(temp_path, CLUSTER_DATA_PATH)
    last_cluster_repository_update = CLUSTER_DATA_PATH.stat().st_mtime


def read_base_repositories():
    read_base_entity_repository()
    read_base_cluster_repository()


def write_base_repositories():
    write_base_entity_repository()
    write_base_cluster_repository()


app = FastAPI(
    title="Cluster Repository",
    description="A service for managing clusters.",
    version="1.0.0",
    root_path="/api/v1/clusters",
    root_path_in_servers=True
)

if SYSTEM_TYPE == "base":
    app.add_middleware(
        FileLockerMiddleware,
        files_to_lock=[DATA_PATH / "entity_repository.json", DATA_PATH / "cluster_repository.json"],
        before=read_base_repositories, after=write_base_repositories)


@app.on_event("startup")
async def startup_event():
    if SYSTEM_TYPE == "neo4j":
        neo4j_repositories()

    elif SYSTEM_TYPE == "base":
        read_base_repositories()


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


def _base_cluster_to_clusterOut(cluster: ClusterModel) -> ClusterOut:
    return ClusterOut(
        cluster_id=cluster.cluster_id,
        cluster_name=cluster.cluster_name,
        entity_ids=[entity.entity_id for entity in cluster.entities],
        cluster_vector=cluster.cluster_vector
    )


@app.get("/", response_model=list[ClusterOut])
async def get_all_clusters(user: dict = Security(auth_required, scopes=[])):
    _all_clusters: list[ClusterModel] = cluster_repository.get_all_clusters()
    return [
        _base_cluster_to_clusterOut(cluster)
        for cluster in _all_clusters
    ]


@app.get("/cluster/{cluster_id}", response_model=ClusterOut)
async def get_cluster_by_id(cluster_id: str, user: dict = Security(auth_required, scopes=[])):
    try:
        cluster: ClusterModel = cluster_repository.get_cluster_by_id(cluster_id)
    except NotFoundException:
        raise HTTPException(status_code=404, detail="Cluster not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return _base_cluster_to_clusterOut(cluster)


@app.post("/cluster/create", response_model=ClusterOut)
async def create_cluster(cluster_in: ClusterIn, user: dict = Security(auth_required, scopes=[])):
    cluster = ClusterModel(
        cluster_id=cluster_in.cluster_id,
        cluster_name=cluster_in.cluster_name,
        entities=[]
    )
    try:
        cluster = cluster_repository.add_cluster(cluster)

    except AlreadyExistsException as e:
        raise HTTPException(status_code=409, detail=e.message)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return _base_cluster_to_clusterOut(cluster)


@app.delete("/cluster/{cluster_id}", status_code=204)
async def delete_cluster(cluster_id: str, user: dict = Security(auth_required, scopes=["admin"])):
    try:
        cluster_repository.delete_cluster(cluster_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return


@app.delete("/delete", status_code=204)
async def delete_clusters(clusters_in: DeleteClustersIn, user: dict = Security(auth_required, scopes=["admin"])):
    try:
        cluster_repository.delete_clusters(clusters_in.cluster_ids)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return


@app.delete("/delete/all", status_code=204)
async def delete_all_clusters(user: dict = Security(auth_required, scopes=["admin"])):
    try:
        cluster_repository.delete_all_clusters()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return


@app.post("/cluster/{cluster_id}/add-entity", response_model=ClusterOut)
async def add_entity_to_cluster(cluster_id: str, entity_id: str, user: dict = Security(auth_required, scopes=[])):
    try:
        cluster_repository.add_entity_to_cluster(cluster_id=cluster_id, entity_id=entity_id)
    except AlreadyExistsException as e:
        raise HTTPException(status_code=409, detail=e.message)
    except AlreadyInClusterException as e:
        raise HTTPException(status_code=409, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    cluster = cluster_repository.get_cluster_by_id(cluster_id)
    return _base_cluster_to_clusterOut(cluster)


@app.post("/cluster/{cluster_id}/add-entities", response_model=ClusterOut)
async def add_entities_to_cluster(cluster_id: str, payload: ClusterAddEntityIn, user: dict = Security(auth_required, scopes=[])):
    try:
        for entity in payload.entity_ids:
            cluster_repository.add_entity_to_cluster(cluster_id=cluster_id, entity_id=entity)
    except AlreadyExistsException as e:
        raise HTTPException(status_code=409, detail=e.message)
    except AlreadyInClusterException as e:
        raise HTTPException(status_code=409, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    cluster = cluster_repository.get_cluster_by_id(cluster_id)
    return _base_cluster_to_clusterOut(cluster)


@app.post("/cluster/{cluster_id}/remove-entity", response_model=ClusterOut)
async def remove_entity_from_cluster(cluster_id: str, entity_id: str, user: dict = Security(auth_required, scopes=[])):
    try:
        cluster_repository.remove_entity_from_cluster(entity_id=entity_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    cluster = cluster_repository.get_cluster_by_id(cluster_id)
    return _base_cluster_to_clusterOut(cluster)


@app.get("/export/csv", response_class=FileResponse)
async def export_clusters_csv(user: dict = Security(auth_required, scopes=["admin"])):
    _all_clusters: list[ClusterModel] = cluster_repository.get_all_clusters()
    pd.DataFrame([
        {
            'cluster_id': cluster.cluster_id,
            'cluster_name': cluster.cluster_name,
            'entity_ids': [entity.entity_id for entity in cluster.entities],
            'cluster_vector': cluster.cluster_vector.tolist()
        }
        for cluster in _all_clusters
    ]).to_csv(
        './tmp/clusters.csv',
        index=False
    )
    return FileResponse('./tmp/clusters.csv',
                        filename='clusters.csv',
                        media_type='text/csv')
