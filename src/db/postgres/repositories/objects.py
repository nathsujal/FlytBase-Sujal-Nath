import json
from typing import List, Dict

from src.schemas import Object
from ..connection import get_writer
from src.utils import get_logger

logger = get_logger(__name__)


def save_objects(objects: List[Object]):
    """Save all objects to the database."""
    if objects is None or len(objects) == 0:
        logger.debug("No objects to save")
        return
    
    logger.debug(f"Saving {len(objects)} objects to the database")
    
    with get_writer() as conn:
        with conn.cursor() as cursor:
            cursor.executemany("""
                INSERT INTO objects (id, label)
                VALUES (%s, %s)
                ON CONFLICT (id) DO NOTHING
            """, [
                (obj.object_id, obj.label)
                for obj in objects
            ])
            updated_rows = cursor.rowcount
    
    logger.info(f"Saved {updated_rows}/{len(objects)} objects to the database")


def save_object_attributes(object_id: int, attributes: Dict[str, str]):
    """Save object attributes to the database."""
    if object_id is None:
        logger.debug("No object id")
        return
    if attributes is None or len(attributes) == 0:
        logger.debug("No attributes")
        return
    
    logger.debug(f"Saving attributes for object {object_id}:\n{json.dumps(attributes)}")
    
    with get_writer() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE objects
                SET attributes = COALESCE(attributes, '{}'::jsonb) || %s::jsonb
                WHERE id = %s
            """, (Json(attributes), object_id))
    logger.info(f"Saved {len(attributes)} attributes for object {object_id}")
        