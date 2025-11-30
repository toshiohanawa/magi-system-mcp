FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/workspace/src \
    PORT=8787

RUN adduser --disabled-password --gecos "" mcp
WORKDIR /workspace

COPY requirements.txt /workspace/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY src /workspace/src
COPY host_wrappers /workspace/host_wrappers
COPY scripts /workspace/scripts
COPY openapi.json /workspace/openapi.json

USER mcp

EXPOSE 8787

CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8787"]
