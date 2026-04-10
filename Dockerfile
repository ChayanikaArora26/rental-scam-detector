FROM python:3.11-slim

# System deps for pdfplumber / lxml / spaCy
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libgl1 curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Copy source
COPY . .

# Create data dirs
RUN mkdir -p data/cuad data/au_tenancy_forms data/processed

# Pre-download data + bake embedding cache into the image at build time.
# This means runtime just loads a .npy file (~40MB) instead of encoding
# 10k texts on startup — keeps RAM well under 512MB.
RUN python - <<'EOF'
import download_data
download_data.run()

from rental_scam_detector import (
    RentalScamDetector, load_cuad, load_forms_and_chunk, FORMS_DIR, EMBED_CACHE
)

if not EMBED_CACHE.exists():
    print("Building embedding cache at image build time...")
    _, cuad_texts = load_cuad()
    au_texts = [r["text"] for r in load_forms_and_chunk(FORMS_DIR)]
    RentalScamDetector(au_texts + cuad_texts)
    print("Cache saved:", EMBED_CACHE)
else:
    print("Cache already exists, skipping.")
EOF

EXPOSE 8000

CMD uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
