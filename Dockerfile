FROM python:3.11-slim

# System deps for pdfplumber / lxml / spaCy
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libgl1 curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer-cached)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Copy source
COPY . .

# Create data dirs
RUN mkdir -p data/cuad data/au_tenancy_forms data/processed

# Port
EXPOSE 8000

# Uvicorn — workers=1 keeps memory low on free tiers
CMD uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
