FROM python:3.10-slim

WORKDIR /code

ENV PYTHONPATH=/code
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apk update
RUN apk add libpq 
RUN apk add --virtual .build-deps gcc musl-dev python3-dev postgresql16-client postgresql-dev openssl-dev libffi-dev gdal-dev geos-dev g++ gettext
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
RUN mkdir -p static media
EXPOSE 8000
COPY . .
COPY ./docker/local_settings.py /code/website/local_settings.py

