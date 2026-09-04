# CryptoAID Trade AI — Production Container
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency specifications
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt web3 eth-account

# Copy application source and scripts
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY README.md .env.example ./

# Create data volume directory
RUN mkdir -p /app/data

# Environment Defaults
ENV APP_ENV=production
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Default entrypoint runs FastAPI API worker and static files
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
