#!/bin/bash

# Create base image for microservices

docker build -t eec_microservice_base .

# Build the microservices

docker build -t eec_auth ./services/authentication_service

docker build -t eec_entity ./services/entity_service

docker build -t eec_cluster ./services/cluster_service

docker build -t eec_mention ./services/mention_clustering_service

docker build -t eec_user ./services/user_service


# Run the microservices

docker-compose up --build --force-recreate -d