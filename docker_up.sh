#!/bin/bash

# Create base image for microservices

docker build -t eec_microservice_base .

# Build the microservices

docker build -t eec_auth ./services/authentication_service

docker build -t eec_entity ./services/entity_service


# Run the microservices

docker-compose up --build -d