import cv2
from typing import List

from src.schemas import Frame
from ..connection import get_writer
from src.config import settings
from src.utils import get_logger

logger = get_logger(__name__)


def save_frames(frames: List[Frame]):
    """Save all frames to the database."""
    if frames is None or len(frames) == 0:
        logger.debug("No frames to save")
        return
    
    logger.debug(f"Saving {len(frames)} frames to the database")

    # Prepare the data
    rows = []
    for frame in frames:
        image_path = f"{settings.image_storage_path}/{frame.frame_id:6d}.jpg"
        cv2.imwrite(str(image_path), frame.image)
        rows.append((
            frame.frame_id,
            frame.timestamp_sec,
            frame.captured_at,
            str(image_path)
        ))

    with get_writer() as conn:
        with conn.cursor() as cursor:
            cursor.executemany("""
                INSERT INTO frames
                (id, timestamp_sec, captured_at, image_path)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, rows)
            
            updated_rows = cursor.rowcount
    logger.info(f"Saved {updated_rows}/{len(frames)} frames to the database")


def update_novel_frames(frames: List[Frame]):
    """Update novel frames."""
    if frames is None or len(frames) == 0:
        logger.debug("No frames to update")
        return
    
    logger.debug(f"Updating {len(frames)} frames")
    
    with get_writer() as conn:
        with conn.cursor() as cursor:
            cursor.executemany("""
                UPDATE frames
                SET is_novel = true,
                    frame_description = %s,
                    attributes = COALESCE(attributes, '{}'::jsonb) || %s::jsonb
                WHERE id = %s
            """, [
                (frame.caption, Json(frame.attributes), frame.frame_id)
                for frame in frames
            ])
            updated_rows = cursor.rowcount
    logger.info(f"Updated {updated_rows}/{len(frames)} novel frames")