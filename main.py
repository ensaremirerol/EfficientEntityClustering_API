from services.mention_clustering_service.mention_clustering import mention_clustering_router
from services.cluster_service.cluster_service import cluster_router
from services.entity_service.entity_service import entities_router
from fastapi import FastAPI
from pathlib import Path
from eec import EntityClustererBridge
import json
import os
import uvicorn
import logging
from logging.handlers import RotatingFileHandler
import sys


# TODO: DUplicate logging

LOGGER_PATH = Path(os.getenv("LOGGER_PATH") or "./")

if not LOGGER_PATH.exists():
    LOGGER_PATH.mkdir()

if not (LOGGER_PATH / "main.log").exists():
    with open(LOGGER_PATH / "main.log", "w") as f:
        f.write("")
        f.close()

logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOGGER_PATH / "main.log"),
              RotatingFileHandler(LOGGER_PATH / "main.log", maxBytes=1000000, backupCount=5)])


def exception_handler(request, exc):
    logging.exception("Uncatched exception!\n{}".format(exc))


sys.excepthook = exception_handler

app = FastAPI()

app.include_router(entities_router, prefix="/entities", tags=["entities"])
app.include_router(cluster_router, prefix="/clusters", tags=["clusters"])
app.include_router(mention_clustering_router, prefix="/mention_clustering",
                   tags=["mention_clustering"])


@app.get("/")
async def root():
    return {"message": "Hello World"}


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
def check_files():
    logging.info("Checking files...")
    _env_data = os.getenv("DATA_PATH") or "data"
    data_path = Path(_env_data)

    if not data_path.exists():
        data_path.mkdir()

    return data_path


def load_data():
    logging.info("Loading data...")
    data_path = check_files()

    # Load config
    config_path = data_path / "config.json"
    if not config_path.exists():
        logging.error("Config file not found")
        exit(1)
    with open(config_path, "r") as f:
        config = json.load(f)
    logging.info("Config loaded")

    if config['type'] == 'base':
        from eec import BaseEntityRepository, BaseClusterRepository
        from gensim.models import KeyedVectors

        # Load Word2Vec model
        model_path = data_path / config['word2vec_file']
        if not model_path.exists():
            logging.error("Model file not found")
            exit(1)
        model = KeyedVectors.load(str(model_path))
        logging.info("Model loaded")
        # Load entities
        entities_path = data_path / "entities.json"
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
        clusters_path = data_path / "clusters.json"
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

        method = None

        if config['method_config']['method'] == 'base':
            from eec import BaseMentionClusteringMethod
            method = BaseMentionClusteringMethod(
                name='base',
                entity_repository=entity_repo,
                cluster_repository=cluster_repo,
            )

        EntityClustererBridge().set_cluster_repository(cluster_repo)
        EntityClustererBridge().set_entity_repository(entity_repo)
        EntityClustererBridge().set_mention_clustering_method(method)
# endregion

# region Save data


def save_data():
    logging.info("Saving data...")
    data_path = check_files()

    # Save entities
    entities_path = data_path / "entities.json"
    with open(entities_path, "w") as f:
        json.dump(EntityClustererBridge().entity_repository.to_dict(), f)
    logging.info("Entities saved")

    # Save clusters
    clusters_path = data_path / "clusters.json"
    with open(clusters_path, "w") as f:
        json.dump(EntityClustererBridge().cluster_repository.to_dict(), f)
    logging.info("Clusters saved")

# endregion


if __name__ == "__main__":
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    logging.getLogger("uvicorn").addHandler(handler)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info",
                log_config=logging.basicConfig(level=logging.INFO, filename=LOGGER_PATH / "main.log",))
