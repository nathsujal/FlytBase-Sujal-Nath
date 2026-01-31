"""PostgreSQL collector for security pattern detection."""
from typing import List, Dict, Any
from src.db.postgres.connection import get_reader
from src.utils import get_logger

logger = get_logger(__name__)


def get_loitering_objects(threshold_seconds: float = 60.0) -> List[Dict[str, Any]]:
    """
    Get objects that were present for longer than the threshold time.
    
    Loitering is detected by calculating the time span between an object's
    first and last appearance in the video feed.
    
    Args:
        threshold_seconds: Minimum duration (in seconds) to consider as loitering
        
    Returns:
        List of dicts with object_id, label, duration_sec, first_seen, last_seen
    """
    logger.debug(f"Querying loitering objects with threshold: {threshold_seconds}s")
    
    query = """
        SELECT 
            o.id AS object_id,
            o.label,
            MAX(f.timestamp_sec) - MIN(f.timestamp_sec) AS duration_sec
        FROM objects o
        JOIN events e ON o.id = e.object_id
        JOIN frames f ON e.frame_id = f.id
        WHERE o.label = 'person'
        GROUP BY o.id, o.label
        HAVING MAX(f.timestamp_sec) - MIN(f.timestamp_sec) > %s
        ORDER BY duration_sec DESC
    """
    
    with get_reader() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (threshold_seconds,))
            columns = [desc[0] for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    logger.info(f"Found {len(results)} loitering objects (>{threshold_seconds}s)")
    return results


def get_vehicle_ids() -> List[Dict[str, Any]]:
    """
    Get IDs and labels of all unique vehicle objects from the database.
    
    Vehicles include cars, motorcycles, and bicycles.
    
    Returns:
        List of dictionaries containing 'id' and 'label'.
    """
    logger.debug("Querying all vehicle object IDs")
    
    query = """
        SELECT id, label
        FROM objects 
        WHERE label IN ('car', 'motorcycle', 'bicycle')
    """
    
    try:
        with get_reader() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                return [{"id": row[0], "label": row[1]} for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error retrieving vehicles: {e}")
        return []


def get_off_hours_activity(start_hour: int = 22, end_hour: int = 5) -> List[Dict[str, Any]]:
    """
    Get objects detected during off-hours (e.g., midnight to 5 AM).
    
    Args:
        start_hour: Start of off-hours window (0-23)
        end_hour: End of off-hours window (0-23)
        
    Returns:
        List of dicts with object details and timestamps
    """
    logger.debug(f"Querying off-hours activity between {start_hour}:00 - {end_hour}:00")
    
    # Handle midnight-crossing ranges (e.g., 22:00 to 05:00)
    if start_hour > end_hour:
        # Crosses midnight: hour >= start OR hour < end
        hour_condition = """
            (EXTRACT(HOUR FROM f.captured_at) >= %s
             OR EXTRACT(HOUR FROM f.captured_at) < %s)
        """
    else:
        # Normal range: hour >= start AND hour < end
        hour_condition = """
            (EXTRACT(HOUR FROM f.captured_at) >= %s
             AND EXTRACT(HOUR FROM f.captured_at) < %s)
        """
    
    query = f"""
        SELECT DISTINCT ON (o.id)
            o.id AS object_id,
            o.label,
            f.captured_at,
            EXTRACT(HOUR FROM f.captured_at) AS hour
        FROM objects o
        JOIN events e ON o.id = e.object_id
        JOIN frames f ON e.frame_id = f.id
        WHERE f.captured_at IS NOT NULL
          AND {hour_condition}
        ORDER BY o.id, f.captured_at
    """

    with get_reader() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (start_hour, end_hour))
            columns = [desc[0] for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    logger.info(f"Found {len(results)} off-hours detections")
    return results
