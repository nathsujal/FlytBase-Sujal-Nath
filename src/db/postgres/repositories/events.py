from ..connection import get_writer
from src.utils import get_logger

logger = get_logger(__name__)

def save_event(object_id: int, frame_id: int, event_description: str):
    """Save an event to the database."""
    if object_id is None:
        logger.debug("No object id")
        return
    if frame_id is None:
        logger.debug("No frame id")
        return
    if not event_description:
        logger.debug("No event description")
        return
    
    logger.debug(f"Saving event '{event_description}' | Object id: {object_id} | Frame id: {frame_id}")
    
    with get_writer() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO events (object_id, frame_id, event_description)
                VALUES (%s, %s, %s)
                ON CONFLICT (object_id, frame_id) DO NOTHING
            """, (object_id, frame_id, event_description))
    logger.info(f"Saved event for Object id: {object_id} | Frame id: {frame_id}")