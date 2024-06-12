# FROM teamacimisai/django-mssql-base-image-python3.12:latest
FROM python:3.12-slim-bullseye

WORKDIR /app

# install dependencies
RUN pip install pip --upgrade

# install dependencies
RUN apt-get update && apt-get -y upgrade && apt-get install -y build-essential

COPY requirements.txt .

RUN pip install -r requirements.txt

# copy project
COPY . .
