# Efficient Entity Clustering API

## 🖇️ Purpose

This API designed to be work with Efficient Entity Clustering Application. It is a RESTful API that provides the connection between the application and the algorithm and the database.

## 📚 Requirements

-   Python 3.10 or Docker

## 🚀 Getting Started

## 📝 Environment Variables

-   `DATA_PATH` - Path to the directory where the data will be stored. Default value is `./data`.

-   `LOGGER_PATH` - Path to the directory where the logs will be stored. Default value is `./` (current directory).

## 📝 Configuration

You have to create a data folder for API to use. Also you either provide a .env file or set the environment variables.

## ⚙️ Environment Variables

-   `DATA_PATH` - Path to the directory where the data will be stored. Default value is `./data`. (For docker, you have to mount the volume to this path)

-   `SETUP_TYPE` - Type of setup. It can be either `base` or `neo4j`. Default value is `base`.

-   `WORD2VEC_FILE` - Path to the word2vec file. Default value is `./data/word2vec/word2vec.bin`.

-   `LOGGER_PATH` - Path to the directory where the logs will be stored. Default value is `./` (current directory).

-   `NEO4J_URI` - Uri of the neo4j database. (Needed for `neo4j` setup type)

-   `NEO4J_USER` - User of the neo4j database. (Needed for `neo4j` setup type)

-   `NEO4J_PASSWORD` - Password of the neo4j database. (Needed for `neo4j` setup type)

## 🐳 Docker

### 📦 Build

```bash
docker build -t efficient-entity-clustering-api .
```

### 🏃 Run

-   Base config

```bash
docker run -p 8000:8000 \
 -v <HostDir>:/data \
 -e DATA_PATH=/data \
 -e SETUP_TYPE=base \
 -e WORD2VEC_FILE=path/to/word2vec/file \
 -e LOGGER_PATH=/data \
 efficient-entity-clustering-api
```

-   Neo4j config

```bash
docker run -p 8000:8000 \
 -v <HostDir>:/data \
 -e DATA_PATH=/data \
 -e SETUP_TYPE=neo4j \
 -e WORD2VEC_FILE=path/to/word2vec/file \
 -e LOGGER_PATH=/data \
 -e NEO4J_URI=bolt://<neo4j_host>:<neo4j_port> \
 -e NEO4J_USER=<neo4j_user> \
 -e NEO4J_PASSWORD=<neo4j_password> \
 efficient-entity-clustering-api
```

## 🐍 Python

### 📦 Install

```bash
./setup_venv.sh
```

### 🏃 Run

```bash
source .venv/bin/activate
python3 main.py
```
