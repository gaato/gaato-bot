FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends git cmake build-essential libffi-dev libzmq3-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app
RUN pip install --no-cache-dir -r requirements.txt

COPY bots /app/bots

CMD ["python", "-m", "bots"]
