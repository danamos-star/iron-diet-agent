FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen

COPY . .

EXPOSE 8080
EXPOSE 8000
CMD ["uv", "run", "python", "-m", "backend.main"]
