FROM python:3.10.9-slim-bullseye AS base

RUN apt-get update
RUN apt-get -y install libc-dev
RUN apt-get -y install build-essential
RUN pip install -U pip

COPY ./requirements.txt .

RUN pip install -r requirements.txt

COPY ./packages /packages

RUN pip install ./packages/eec/package
RUN pip install ./packages/file_locker_middleware/
