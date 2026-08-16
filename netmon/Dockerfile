FROM python:3.12-slim

# Install ping utility
RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Data directory for SQLite DB
RUN mkdir -p /data

ENV DB_PATH=/data/netmon.db
ENV CHECK_INTERVAL=10
ENV PING_HOST=8.8.8.8
ENV PING_HOST2=1.1.1.1

EXPOSE 5000

CMD ["python", "app.py"]
