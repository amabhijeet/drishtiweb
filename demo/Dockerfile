FROM node:22-slim AS map
WORKDIR /build
COPY package*.json prepare-map.cjs ./
RUN npm ci

FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /portal
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py gps.py mysql_db.py ./
COPY templates templates
COPY static static
COPY --from=map /build/static/vendor static/vendor
COPY demo demo
USER 10001:10001
CMD ["sh","-ec","python -m demo.seed && exec gunicorn --workers 1 --threads 4 --timeout 240 --bind 0.0.0.0:8080 demo.portal:app"]
