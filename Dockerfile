FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN useradd --system --uid 10001 --no-create-home app \
    && mkdir -p /srv/data && chown app:app /srv/data
COPY app ./app
COPY content ./content
ENV DB_PATH=/srv/data/app.db
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
