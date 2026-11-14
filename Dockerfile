FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml ./

RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir fastapi uvicorn

COPY src/ ./src/
COPY run_server.py ./

ENV PORT=8765
ENV HOST=0.0.0.0
EXPOSE 8765

CMD ["python3", "-m", "src.web_server"]
