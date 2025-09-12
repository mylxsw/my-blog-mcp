FROM ghcr.io/astral-sh/uv:python3.13-trixie-slim

WORKDIR /app

COPY pyproject.toml .
COPY uv.lock .

RUN uv sync

EXPOSE 8000

COPY . .

CMD ["uv", "run", "server.py"]
