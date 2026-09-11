# syntax=docker/dockerfile:1

# Matches the Python version used in CI (.github/workflows/tests.yml).
# Every compiled dependency (asyncmy, psutil, greenlet) ships manylinux
# wheels, so the slim image needs no build toolchain.
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Tehran time is used throughout the bot; keep the container clock consistent.
    TZ=Asia/Tehran

WORKDIR /app

# Dependencies first so this layer is cached across source-only changes.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Never run as root inside the container.
RUN useradd --create-home --shell /usr/sbin/nologin bot \
    && chown -R bot:bot /app \
    && chmod +x docker/entrypoint.sh
USER bot

# Long-polling worker: no ports are exposed. Deploy as a worker service.
ENTRYPOINT ["./docker/entrypoint.sh"]
CMD ["python", "main.py"]
