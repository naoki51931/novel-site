FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV DB_HOST=db
ENV DB_USER=novel_user
ENV DB_PASS=novel_pass
ENV DB_NAME=novel_db

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
