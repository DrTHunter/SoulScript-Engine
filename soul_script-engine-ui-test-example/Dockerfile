FROM python:3.11-slim

WORKDIR /app

# Install system deps for FAISS (libgomp needed for OpenMP)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY soul_script-engine-ui-test-example/ ./soul_script-engine-ui-test-example/

WORKDIR /app/soul_script-engine-ui-test-example

EXPOSE 8989

CMD ["python", "-m", "uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8989"]
