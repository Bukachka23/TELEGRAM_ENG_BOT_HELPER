FROM python:3.11-slim-buster

RUN apt-get -y update && apt-get -y upgrade && apt-get install -y --no-install-recommends ffmpeg

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

COPY src/data/eng_words.txt src/data/eng_words.txt
COPY src/data/ger_words.txt src/data/ger_words.txt

RUN touch .env

ENV PYTHONPATH "${PYTHONPATH}:/app"

CMD ["python", "src/main.py"]