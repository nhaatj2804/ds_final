# -----------------------------
# Dockerfile for FastAPI Movie Recommender (Cloud Run Gen2)
# -----------------------------

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy app source code
COPY app ./app

# Copy data folder
COPY data ./data

# Copy dependency files first (Docker cache optimization)
COPY requirements.txt .

# Upgrade pip
RUN pip install --upgrade pip

# Install CPU-only PyTorch first (faster, avoids torch + other packages conflicts)
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies
RUN pip install --no-cache-dir --progress-bar=on -r requirements.txt

# Copy app source code
COPY app ./app

# Expose the port (optional, mostly for documentation)
EXPOSE 8000


# Start FastAPI using Cloud Run PORT
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
