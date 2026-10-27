FROM python:3.12-slim

# ffmpeg com libass (legendas) + fonte usada nas legendas
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Baixa o modelo do Whisper no build: o container sobe pronto, sem esperar download
ARG WHISPER_MODEL=base
ENV WHISPER_MODEL=${WHISPER_MODEL} \
    HF_HOME=/opt/hf \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('${WHISPER_MODEL}', device='cpu', compute_type='int8')"

COPY app ./app

# Railway define $PORT; 1 processo uvicorn (a fila de jobs vive dentro dele)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
