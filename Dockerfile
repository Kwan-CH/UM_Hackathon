FROM python:3.13-slim

WORKDIR /app

RUN python -m venv venv

COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app ./app