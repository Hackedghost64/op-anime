# Use a slim Python image to keep the container lightweight
FROM python:3.11-slim

# Defensive Programming: Ensure system dependencies for the bash script exist
RUN apt-get update && apt-get install -y \
    bash \
    curl \
    grep \
    sed \
    fzf \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /server

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application
COPY . .

# Ensure the bash script is executable
RUN chmod +x /server/bin/ani-cli

# Expose the port Railway expects
EXPOSE 8000

# Start the FastAPI server using Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
