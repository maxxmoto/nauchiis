# rebuild: tg-preview
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
RUN mkdir -p static

COPY index.html articles-data.js manifest.json robots.txt sitemap.xml terms.html ai-disclaimer.html ./static/
COPY static ./static/static

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1/healthz')" || exit 1

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "80"]
