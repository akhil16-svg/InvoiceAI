FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl tesseract-ocr && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data/users

EXPOSE 8502

HEALTHCHECK CMD curl --fail http://localhost:8502/_stcore/health || exit 1

CMD ["streamlit", "run", "main.py", "--server.port=8502", "--server.address=0.0.0.0"]
