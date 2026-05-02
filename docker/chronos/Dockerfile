FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore \
    CBD_CHRONOS_PYTHON=/usr/local/bin/python

WORKDIR /worker

RUN python -m pip install --upgrade pip && \
    python -m pip install --index-url https://download.pytorch.org/whl/cpu torch && \
    python -m pip install chronos-forecasting

COPY docker/chronos/worker_ready.py ./worker_ready.py

CMD ["python", "worker_ready.py"]
