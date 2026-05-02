FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN python -m pip install --upgrade pip

COPY pyproject.toml README.md LICENSE ./
COPY continuity_break_detector ./continuity_break_detector

RUN python -m pip install -e '.[test]'

COPY . .

CMD ["pytest", "-q"]
