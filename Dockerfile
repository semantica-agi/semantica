FROM node:25-alpine AS frontend-builder

WORKDIR /app/semantica-explorer


COPY semantica-explorer/package.json semantica-explorer/package-lock.json* ./


RUN npm install


COPY semantica-explorer/ ./
RUN npm run build


FROM python:3.12-slim AS runtime

WORKDIR /app

COPY pyproject.toml ./
COPY semantica/ ./semantica/

COPY --from=frontend-builder /app/semantica/static ./semantica/static

RUN pip install --no-cache-dir ".[explorer]"

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "semantica.explorer.app:app", "--host", "0.0.0.0", "--port", "8000"]