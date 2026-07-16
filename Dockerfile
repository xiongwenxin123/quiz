FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir '.[api,extract]'

USER 65534:65534
EXPOSE 8000
CMD ["uvicorn", "polyglot_quiz.api:app", "--host", "0.0.0.0", "--port", "8000"]

