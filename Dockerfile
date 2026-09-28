FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot ./bot
# config.yaml is mounted or baked in at deploy time; tokens come from env vars.
CMD ["python", "-m", "bot.main"]
