# Efficient Entity Clustering API

## 🖇️ Purpose

This API designed to be work with Efficient Entity Clustering Application. It is a RESTful API that provides the connection between the application and the algorithm and the database.

## 📚 Requirements

-   Python 3.10 or Docker

## 🚀 Getting Started

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
python3 main.py
```

## 📝 Environment Variables

-   `DATA_PATH` - Path to the directory where the data will be stored.

-   `LOGGER_PATH` - Path to the directory where the logs will be stored.
