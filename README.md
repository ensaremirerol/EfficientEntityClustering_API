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

You have to create a data folder for API to use. And data folder must contain a `config.json` file. You can find an [example configuration](example_config.json) file in the repository.

Also, data folder should contain Word2Vec model file. You specify the name of the file in the configuration file.

## 🐳 Docker

### 📦 Build

```bash
docker build -t efficient-entity-clustering-api .
```

### 🏃 Run

```bash
docker run -p 8000:8000 \
 -v <HostDir>:/data \
 -e DATA_PATH=/data \
 -e LOGGER_PATH=/data \
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
