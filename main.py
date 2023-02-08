from fastapi import FastAPI
from pathlib import Path
from eec import EntityClustererBridge
import json
import os
app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.on_event("startup")
async def startup_event():
    print("Starting up...")
    load_data()
    print("Data loaded")


@ app.on_event("shutdown")
async def shutdown_event():
    print("Shutting down...")
    save_data()
    print("Data saved")


# region Load data
def check_files():
    print("Checking files...")
    _env_data = os.getenv("DATA_PATH") or "data"
    data_path = Path(_env_data)

    if not data_path.exists():
        data_path.mkdir()

    return data_path


def load_data():
    print("Loading data...")
    data_path = check_files()

    # Load config
    config_path = data_path / "config.json"
    if not config_path.exists():
        print("Config file not found")
        exit(1)
    with open(config_path, "r") as f:
        config = json.load(f)
    print("Config loaded")

    if config['type'] == 'base':
        from eec import BaseEntityRepository, BaseClusterRepository
        from gensim.models import KeyedVectors

        # Load Word2Vec model
        model_path = data_path / config['word2vec_file']
        if not model_path.exists():
            print("Model file not found")
            exit(1)
        model = KeyedVectors.load(str(model_path))
        print("Model loaded")
        # Load entities
        entities_path = data_path / "entities.json"
        entity_repo = None
        if not entities_path.exists():
            print("Entities file not found")
            print("Creating empty entities object")
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
            print("Clusters file not found")
            print("Creating empty clusters object")
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
    print("Saving data...")
    data_path = check_files()

    # Save entities
    entities_path = data_path / "entities.json"
    with open(entities_path, "w") as f:
        json.dump(EntityClustererBridge().entity_repository.to_dict(), f)
    print("Entities saved")

    # Save clusters
    clusters_path = data_path / "clusters.json"
    with open(clusters_path, "w") as f:
        json.dump(EntityClustererBridge().cluster_repository.to_dict(), f)
    print("Clusters saved")

# endregion
