FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV CMAKE_ARGS="-DGGML_CUDA=OFF -DGGML_OPENBLAS=ON"
ENV FORCE_CMAKE=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential cmake libopenblas-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY server.py .

EXPOSE 8000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "120"]
