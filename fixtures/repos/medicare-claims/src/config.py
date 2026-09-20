from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
BRONZE_DIR = DATA_DIR / "bronze"
SILVER_DIR = DATA_DIR / "silver"
GOLD_DIR = DATA_DIR / "gold"

CMS_DATASET_VERSION_ID = "8ba584c6-a43a-4b0b-a35a-eb9a59e3a571"
CMS_API_BASE = "https://data.cms.gov/data-api/v1/dataset"
CMS_PAGE_SIZE = 5000
CMS_MAX_ROWS = 50000

NPPES_API_BASE = "https://npiregistry.cms.hhs.gov/api/"
NPPES_MAX_PROVIDERS = 300

DATA_YEAR = 2023
