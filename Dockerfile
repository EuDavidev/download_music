FROM python:3.11-slim

# Install ffmpeg, curl, and nodejs (for yt-dlp JS challenge solving)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl nodejs && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose port
EXPOSE 8000

ENV NO_BROWSER=1
ENV PORT=8000

# Start server
CMD ["python", "run_web.py"]
