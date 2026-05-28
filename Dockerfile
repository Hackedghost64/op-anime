FROM python:3.11-slim

# System deps required by ani-cli: curl, sed, grep for scraping,
# openssl for provider response decryption (aes-256-ctr),
# fzf as a fallback dep-check requirement, ffmpeg for m3u8 handling.
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    grep \
    sed \
    fzf \
    ffmpeg \
    openssl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /server

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Both scripts must be executable
RUN chmod +x /server/bin/ani-cli /server/bin/ani-cli-api.sh

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
