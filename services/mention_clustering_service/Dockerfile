
FROM eec_microservice_base

COPY . /app

WORKDIR /app

# Entry point for FastAPI

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004"]

EXPOSE 8004