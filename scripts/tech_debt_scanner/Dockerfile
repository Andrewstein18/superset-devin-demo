FROM python:3.12-slim

WORKDIR /app

# No external dependencies needed — stdlib only (json, urllib, logging, etc.)
COPY orchestrator.py __init__.py ./scripts/tech_debt_scanner/

# Create reports directory
RUN mkdir -p /app/reports

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "scripts.tech_debt_scanner.orchestrator"]
