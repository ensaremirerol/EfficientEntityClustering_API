FROM python:3.10.9 AS base

ENV DATA_PATH="/data"

COPY . /app

WORKDIR /app

RUN apt-get update
RUN apt-get -y install libc-dev
RUN apt-get -y install build-essential
RUN pip install -U pip

RUN pip install -r requirements.txt

RUN pip install ./packages/eec/src

# Entry point for FastAPI

ENTRYPOINT ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000" ]

EXPOSE 8000