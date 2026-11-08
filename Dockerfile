FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY proto ./proto
COPY scripts ./scripts
COPY src ./src
RUN python scripts/generate_stubs.py

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "pulso_ai.server"]
