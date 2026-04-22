FROM pandoc/extra:latest-ubuntu

# Install Python
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

# Only copy app code and static assets
# Templates, licenses, and pandoc templates are fetched from GitHub at runtime
COPY main.py .
COPY static/ ./static/

EXPOSE 8000

# Override pandoc entrypoint
ENTRYPOINT []
CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
