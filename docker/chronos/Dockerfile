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
COPY docker/chronos/smoke_test.py ./smoke_test.py
COPY docker/chronos/predict.py ./predict.py
COPY continuity_break_detector/__init__.py ./continuity_break_detector/__init__.py
COPY continuity_break_detector/prediction_schema.py ./continuity_break_detector/prediction_schema.py

CMD ["python", "worker_ready.py"]
