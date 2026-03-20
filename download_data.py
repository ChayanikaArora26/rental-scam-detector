"""
download_data.py — Run once on first startup to fetch required data files.

Called automatically by api.py lifespan if files are missing.
Safe to re-run; skips anything already downloaded.
"""

import pathlib
import shutil
import sys

BASE  = pathlib.Path(__file__).parent
DATA  = BASE / "data"
CUAD_PATH  = DATA / "cuad" / "CUAD_v1" / "CUAD_v1.json"
FORMS_DIR  = DATA / "au_tenancy_forms"
FORMS_DIR.mkdir(parents=True, exist_ok=True)

NSW_FORM_URL = (
    "https://www.fairtrading.nsw.gov.au/__data/assets/pdf_file/0004/383525/"
    "Residential-tenancy-agreement.pdf"
)


def ensure_cuad() -> bool:
    if CUAD_PATH.exists():
        print(f"  CUAD already present ({CUAD_PATH})")
        return True
    print("  Downloading CUAD dataset from HuggingFace (~38 MB)…")
    try:
        from huggingface_hub import hf_hub_download
        path = hf_hub_download(
            repo_id="theatticusproject/cuad",
            filename="CUAD_v1/CUAD_v1.json",
            repo_type="dataset",
            local_dir=str(DATA / "cuad"),
        )
        print(f"  CUAD saved to {path}")
        return True
    except Exception as e:
        print(f"  WARNING: Could not download CUAD: {e}")
        print("  The detector will still work using only the AU tenancy form as reference.")
        return False


def ensure_nsw_form() -> bool:
    existing = list(FORMS_DIR.glob("*.pdf"))
    if existing:
        print(f"  AU tenancy form already present ({existing[0].name})")
        return True
    print("  Downloading NSW Residential Tenancy Agreement…")
    try:
        import requests
        r = requests.get(NSW_FORM_URL, timeout=15,
                         headers={"User-Agent": "Mozilla/5.0"}, allow_redirects=True)
        if r.status_code == 200:
            dest = FORMS_DIR / "nsw_tenancy_agreement.pdf"
            dest.write_bytes(r.content)
            print(f"  NSW form saved ({len(r.content)//1024} KB)")
            return True
        else:
            print(f"  WARNING: Got HTTP {r.status_code} for NSW form")
    except Exception as e:
        print(f"  WARNING: Could not download NSW form: {e}")
    return False


def ensure_nltk():
    import nltk
    # Download both quietly; safe to call even if already present
    for resource in ("punkt", "punkt_tab"):
        try:
            nltk.download(resource, quiet=True)
        except Exception as e:
            print(f"  WARNING: NLTK {resource} download failed: {e}")


def run():
    print("=== Data bootstrap ===")
    ensure_nltk()
    ensure_cuad()
    ensure_nsw_form()
    print("=== Done ===")


if __name__ == "__main__":
    run()
