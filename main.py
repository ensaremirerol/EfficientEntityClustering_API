from services.mention_clustering_service.mention_clustering import mention_clustering_router
from services.cluster_service.cluster_service import cluster_router
from services.entity_service.entity_service import entities_router
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio
from pathlib import Path
from eec import EntityClustererBridge
import json
import os
import uvicorn
import logging
from logging.handlers import RotatingFileHandler
import sys
from utils.SIGINT_handler import SIGINTHandler
from dotenv import load_dotenv
load_dotenv()

LOGGER_PATH = Path(os.getenv("LOGGER_PATH") or "./")
SETUP_TYPE = os.getenv("SETUP_TYPE") or "base"
DATA_PATH = Path(os.getenv("DATA_PATH") or "data")
WORD2VEC_FILE = Path(os.getenv("WORD2VEC_FILE") or "word2vec.model")

if not LOGGER_PATH.exists():
    LOGGER_PATH.mkdir()

if not (LOGGER_PATH / "main.log").exists():
    with open(LOGGER_PATH / "main.log", "w") as f:
        f.write("")
        f.close()

logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(LOGGER_PATH / "main.log", maxBytes=1000000, backupCount=5)])


app = FastAPI()

app.include_router(entities_router, prefix="/entities", tags=["entities"])
app.include_router(cluster_router, prefix="/clusters", tags=["clusters"])
app.include_router(mention_clustering_router, prefix="/mention_clustering",
                   tags=["mention_clustering"])


def exception_handler(request, exc):
    logging.error(exc)


app.add_exception_handler(Exception, exception_handler)


@app.get("/")
async def root():
    return {"message": "Hello World"}


async def log_reader(n=100):
    log_lines = []
    with open(LOGGER_PATH / 'main.log', "r") as file:
        log_lines = file.readlines()[-n:]
        return log_lines


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await asyncio.sleep(1)
            log_lines = await log_reader()
            await websocket.send_text("\n".join(log_lines))
    except WebSocketDisconnect:
        logging.info("Websocket disconnected")
    finally:
        await websocket.close()


@app.on_event("startup")
async def startup_event():
    load_data()
    logging.info("Data loaded")


@ app.on_event("shutdown")
async def shutdown_event():
    logging.info("Shutting down...")
    logging.info("Saving data...")
    save_data()
    logging.info("Data saved")
    logging.info(10 * "-" + "Shutdown complete" + 10 * "-")


# region Load data
def check_data_path():
    logging.info("Checking files...")

    if not DATA_PATH.exists():
        raise FileNotFoundError("Data path not found")


def _neo4j_setup():
    from eec import Neo4JClusterRepository, Neo4JEntityRepository, Neo4JMentionClusteringMethod, Neo4JHelper
    from gensim.models import KeyedVectors

    # Load Word2Vec model
    model_path = WORD2VEC_FILE
    if not model_path.exists():
        logging.error("Model file not found")
        exit(1)
    model = KeyedVectors.load(str(model_path))
    logging.info("Model loaded")

    Neo4JHelper(
        uri=os.getenv("NEO4J_URI"),
        user=os.getenv("NEO4J_USER"),
        password=os.getenv("NEO4J_PASSWORD")
    )

    entity_repo = Neo4JEntityRepository(
        keyed_vectors=model
    )
    cluster_repo = Neo4JClusterRepository(
        entity_repository=entity_repo
    )

    method = Neo4JMentionClusteringMethod(
        name='neo4j',
        entity_repository=entity_repo,
        cluster_repository=cluster_repo,
    )

    EntityClustererBridge().set_cluster_repository(cluster_repo)
    EntityClustererBridge().set_entity_repository(entity_repo)
    EntityClustererBridge().set_mention_clustering_method(method)


def _base_setup():
    from eec import BaseEntityRepository, BaseClusterRepository, BaseMentionClusteringMethod
    from gensim.models import KeyedVectors

    # Load Word2Vec model
    model_path = WORD2VEC_FILE
    if not model_path.exists():
        logging.error("Model file not found")
        exit(1)
    model = KeyedVectors.load(str(model_path))
    logging.info("Model loaded")
    # Load entities
    entities_path = DATA_PATH / "entities.json"
    entity_repo = None
    if not entities_path.exists():
        logging.info("Entities file not found")
        logging.info("Creating empty entities object")
        entity_repo = BaseEntityRepository(
            entities=[],
            last_id=0,
            keyed_vectors=model
        )
    else:
        with open(entities_path, "r") as f:
            data = json.load(f)
        entity_repo = BaseEntityRepository.from_dict(
            data=data,
            keyed_vectors=model
        )

    # Load clusters
    clusters_path = DATA_PATH / "clusters.json"
    cluster_repo = None
    if not clusters_path.exists():
        logging.info("Clusters file not found")
        logging.info("Creating empty clusters object")
        cluster_repo = BaseClusterRepository(
            clusters=[],
            entity_repository=entity_repo,
            last_cluster_id=0
        )
    else:
        with open(clusters_path, "r") as f:
            data = json.load(f)
        cluster_repo = BaseClusterRepository.from_dict(
            cluster_repository_dict=data,
            entity_repository=entity_repo
        )

    method = BaseMentionClusteringMethod(
        name='base',
        entity_repository=entity_repo,
        cluster_repository=cluster_repo,
    )

    EntityClustererBridge().set_cluster_repository(cluster_repo)
    EntityClustererBridge().set_entity_repository(entity_repo)
    EntityClustererBridge().set_mention_clustering_method(method)


def load_data():
    logging.info("Loading data...")
    check_data_path()

    if SETUP_TYPE == 'neo4j':
        _neo4j_setup()
    elif SETUP_TYPE == 'base':
        _base_setup()
    else:
        raise ValueError("Invalid type")


# endregion

# region Save data


def save_data():
    if SETUP_TYPE == 'base':
        with SIGINTHandler():
            logging.info("Saving data...")
            check_data_path()

            # Save entities
            entities_path = DATA_PATH / "entities.json.new"
            with open(entities_path, "w") as f:
                json.dump(EntityClustererBridge().entity_repository.to_dict(), f)

            os.remove(DATA_PATH / "entities.json")
            os.rename(entities_path, DATA_PATH / "entities.json")

            logging.info("Entities saved")

            # Save clusters
            clusters_path = DATA_PATH / "clusters.json.new"
            with open(clusters_path, "w") as f:
                json.dump(EntityClustererBridge().cluster_repository.to_dict(), f)

            os.remove(DATA_PATH / "clusters.json")
            os.rename(clusters_path, DATA_PATH / "clusters.json")
            logging.info("Clusters saved")

# endregion


if __name__ == "__main__":
    debug = __debug__
    logging_level = logging.INFO if not os.environ.get("DEBUG") else logging.DEBUG
    reload_flag = True if debug else False
    logging.getLogger("uvicorn").setLevel(logging_level)
    logging.getLogger("fastapi").setLevel(logging_level)
    handler = logging.StreamHandler(sys.stdout)
    logging.getLogger("uvicorn").addHandler(handler)

    uvicorn.run(
        "main:app", host="0.0.0.0", port=8000, reload=reload_flag, log_level=logging_level,
        log_config=logging.basicConfig(
            level=logging.INFO, filename=LOGGER_PATH / "main.log",))
