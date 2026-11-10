# Sandbox image for running generated code. Dependencies are baked in at build
# time because the container runs with --network none.
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN pip install fastapi==0.115.6 sqlalchemy==2.0.36 pydantic==2.10.4 httpx==0.28.1 pytest==8.3.4 \
    && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin runner
USER 10001
WORKDIR /work
ENTRYPOINT []
