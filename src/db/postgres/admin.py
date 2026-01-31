import subprocess
from pathlib import Path

from src.config import settings
from src.utils import get_logger

logger = get_logger(__name__)

SCRIPTS_DIR = Path(__file__).parent / "scripts"


def init_schema():
    """Initialize PostgreSQL schema via shell script."""
    logger.info("Initializing PostgreSQL schema...")
    _run_script(settings.db_setup_script)
    logger.info("PostgreSQL schema initialized")


def _run_script(script_name: str):
    """Execute a shell script."""
    script_path = SCRIPTS_DIR / script_name
    
    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")
    
    result = subprocess.run(["bash", str(script_path)], capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"Script failed: {result.stderr}")
    
    for line in result.stdout.strip().split("\n"):
        if line.strip():
            logger.info(f"  {line}")