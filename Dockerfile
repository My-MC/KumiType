FROM ghcr.io/astral-sh/uv:0.13.5 AS uv
FROM python:3.14.7-slim-bookworm
COPY --from=uv /uv /uvx /usr/local/bin/
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_PROJECT_ENVIRONMENT=/opt/kumitype/.venv
RUN apt-get update && apt-get install -y --no-install-recommends fontconfig libharfbuzz-bin && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/kumitype
COPY uv.lock pyproject.toml README.md LICENSE .python-version ./
COPY src ./src
RUN uv sync --locked --no-dev
ENV PATH="/opt/kumitype/.venv/bin:$PATH" KUMITYPE_CONFIG=/work/config/build.yaml
WORKDIR /work
CMD ["kumitype", "--help"]
