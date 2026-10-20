FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
# SERVICE define qual modulo sobe: cashflow_service | consolidation_service
ARG SERVICE=cashflow_service
ENV SERVICE=${SERVICE}
CMD python -m ${SERVICE}
