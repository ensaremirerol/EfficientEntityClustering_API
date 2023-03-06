from models import MentionOut

from fastapi import FastAPI, Depends, HTTPException,\
    status, Request, Security
from fastapi.security import OAuth2PasswordBearer,\
    OAuth2PasswordRequestForm, SecurityScopes
from fastapi.responses import FileResponse
from file_locker_middleware import FileLockerMiddleware
from eec.core.abstract.entity_repository import IEntityRepository
from eec.core.abstract.cluster_repository import IClusterRepository
from eec.core.abstract.mention_clustering_method import IMentionClusteringMethod
from eec import BaseEntityRepository, Neo4JEntityRepository,\
    BaseClusterRepository, Neo4JClusterRepository, Neo4JHelper,\
    EntityModel, ClusterModel, NotFoundException, \
    AlreadyExistsException, AlreadyInClusterException, Neo4JMentionClusteringMethod, BaseMentionClusteringMethod
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
mention_clustering_method: IMentionClusteringMethod = None
last_entity_repository_update: float = None
last_cluster_repository_update: float = None
o_auth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    scopes={"admin": "Admin access", "editor": "Editor access", "export": "Export access"})


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
    mention_clustering_method = Neo4JMentionClusteringMethod(
        entity_repository=entity_repository,
        cluster_repository=cluster_repository,
        name="Neo4J Mention Clustering Method",
        top_n=10
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
    title="Mention Clustering Service",
    description="A service for reccomending clusters for mentions",
    version="1.0.0",
    root_path="/api/v1/mention",
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
        global entity_repository, cluster_repository, mention_clustering_method
        mention_clustering_method = BaseMentionClusteringMethod(
            entity_repository=entity_repository,
            cluster_repository=cluster_repository,
            name="Base Mention Clustering Method",
            top_n=10
        )


async def auth_required(security_scopes: SecurityScopes, token: dict = Depends(o_auth2_scheme)):
    response = httpx.get(
        f'{AUTH_SERVICE_URL}/verify',
        headers={'Authorization': f"Bearer {token}"}
    )
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if 'admin' in response.json()["scopes"]:
        return response.json()

    if 'admin' in security_scopes.scopes:
        if 'admin' not in response.json()["scopes"]:
            raise HTTPException(status_code=401, detail="Unauthorized")

    for scope in security_scopes.scopes:
        if scope != "admin" and scope not in response.json()["scopes"]:
            raise HTTPException(status_code=401, detail="Unauthorized")

    return response.json()


@app.get("/", response_model=MentionOut)
async def get_prediction_for_next_mention(user: dict = Security(auth_required, scopes=[])):

    try:
        entity: EntityModel = entity_repository.get_random_unlabeled_entity()
    except NotFoundException:
        raise HTTPException(status_code=404, detail="No unlabeled entities found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        possible_clusters = mention_clustering_method.getPossibleClusters(entity)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return MentionOut(
        entity_id=entity.entity_id,
        mention=entity.mention,
        entity_source=entity.entity_source,
        entity_source_id=entity.entity_source_id,
        possible_cluster_ids=[cluster.cluster_id for cluster in possible_clusters],
        possible_cluster_names=[cluster.cluster_name for cluster in possible_clusters]
    )
