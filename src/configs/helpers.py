from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def create_dir_if_not_exists(directory: Path) -> None:
    """Create a directory if it does not exist."""
    try:
        directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"Directory ensured: {directory}")
    except Exception as e:
        logger.error(f"Failed to create directory {directory}: {e}")
