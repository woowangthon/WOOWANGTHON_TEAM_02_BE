from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_DATABASE = PACKAGE_DIR / "data" / "notices.db"
SAMPLE_FILES = {
    "computer": PACKAGE_DIR / "samples" / "computer_sample.html",
    "electrical": PACKAGE_DIR / "samples" / "electrical_sample.html",
}
# Network fetching is intentionally absent until the relevant site administrators
# authorize automated collection.
NETWORK_COLLECTION_ENABLED = False
