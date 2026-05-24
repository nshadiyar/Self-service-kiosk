FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libxcb1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY alembic.ini ./

RUN chmod +x start.sh

# Railway sets PORT dynamically; 8000 is fallback for local docker run
EXPOSE 8000
CMD ["./start.sh"]
