FROM python:3.11-slim

# System deps for pdfplumber / lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libgl1 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer-cached)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Create data dirs
RUN mkdir -p data/cuad data/au_tenancy_forms data/processed

# Pre-download data and generate embedding cache at build time.
# This bakes the .npy file into the image so the server starts in ~200MB RAM
# instead of loading all of CUAD at runtime.
RUN python - <<'EOF'
import download_data
download_data.run()
from rental_scam_detector import (
    load_cuad, load_forms_and_chunk, RentalScamDetector, FORMS_DIR, EMBED_CACHE
)
if not EMBED_CACHE.exists():
    _, cuad_texts = load_cuad()
    au_texts = [r["text"] for r in load_forms_and_chunk(FORMS_DIR)]
    RentalScamDetector(au_texts + cuad_texts)
    print("Embedding cache generated and saved.")
else:
    print("Embedding cache already present, skipping.")
EOF

# Port
EXPOSE 8000

# Uvicorn — workers=1 keeps memory low on free tiers
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
