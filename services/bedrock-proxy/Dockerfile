FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent.py .
COPY host_agent/ host_agent/

ENV HOST_AGENT_BIND=0.0.0.0:7890

EXPOSE 7890

CMD ["python", "agent.py"]
