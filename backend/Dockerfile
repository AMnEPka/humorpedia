FROM python:3.11-slim

WORKDIR /app

# System deps (optional but helps some wheels) + MongoDB tools + dos2unix
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    wget \
    gnupg \
    curl \
    ca-certificates \
    dos2unix \
  && wget -qO - https://www.mongodb.org/static/pgp/server-6.0.asc | gpg --dearmor -o /usr/share/keyrings/mongodb-server-6.0.gpg \
  && echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-6.0.gpg ] https://repo.mongodb.org/apt/debian bullseye/mongodb-org/6.0 main" | tee /etc/apt/sources.list.d/mongodb-org-6.0.list \
  && apt-get update && apt-get install -y --no-install-recommends \
    mongodb-database-tools \
    mongodb-mongosh \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy start script first, fix line endings and make it executable
COPY start.sh /app/start.sh
RUN dos2unix /app/start.sh && chmod +x /app/start.sh

# Copy app code
COPY . /app

EXPOSE 8001

# Use start script for automatic DB restoration
ENTRYPOINT ["/bin/bash", "/app/start.sh"]
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]
