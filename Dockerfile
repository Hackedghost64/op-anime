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
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user with UID 1000 (required for Hugging Face Spaces compatibility)
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=user:user . .

# Ensure bin directory scripts are executable
RUN chmod +x bin/ani-cli bin/ani-cli-api.sh

EXPOSE 7860

CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
