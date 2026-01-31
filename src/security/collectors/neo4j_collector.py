from typing import List, Dict, Any, Optional
from src.db.neo4j.connection import get_session
from src.utils import get_logger

logger = get_logger(__name__)


def get_object_track(object_id: int):
    cypher = """
    MATCH (o:Object {id: $object_id})
    OPTIONAL MATCH (o)-[r]-(n)
    RETURN o, r, n;
    """
    with get_session() as session:
        result = session.run(cypher, object_id=object_id)
        return result.data()


def get_object_timeline(object_id: int) -> Dict[str, Any]:
    """
    Get a timeline report of an object's movements and context over time.
    
    Extracts temporal relationships (those with timestamp/captured_at properties)
    and builds a sorted timeline showing where the object was and what it was
    near/surrounded by at each point in time.
    
    Args:
        object_id: The object ID to track
        
    Returns:
        Dict with object info and sorted timeline of events
    """
    logger.debug(f"Building timeline for object {object_id}")
    
    cypher = """
    MATCH (o:Object {id: $object_id})
    OPTIONAL MATCH (o)-[r]->(n:Value)
    WHERE r.timestamp IS NOT NULL OR r.captured_at IS NOT NULL
    RETURN 
        o.id AS object_id,
        o.label AS label,
        type(r) AS relationship_type,
        r.timestamp AS timestamp,
        r.captured_at AS captured_at,
        r.target_entity_type AS entity_type,
        n.value AS value
    ORDER BY r.timestamp
    """
    
    with get_session() as session:
        result = session.run(cypher, object_id=object_id)
        records = [dict(record) for record in result]
    
    if not records:
        logger.warning(f"No timeline data found for object {object_id}")
        return {"object_id": object_id, "label": None, "timeline": []}
    
    # Build the timeline report
    object_info = {
        "object_id": records[0]["object_id"],
        "label": records[0]["label"]
    }
    
    # Group events by timestamp for a cleaner view
    timeline = []
    for record in records:
        if record["relationship_type"] is None:
            continue
            
        event = {
            "timestamp_sec": record["timestamp"],
            "captured_at": str(record["captured_at"]) if record["captured_at"] else None,
            "relation": record["relationship_type"],
            "entity_type": record["entity_type"],
            "value": record["value"]
        }
        timeline.append(event)
    
    # Sort by timestamp
    timeline.sort(key=lambda x: x["timestamp_sec"] or 0)
    
    report = {
        **object_info,
        "total_events": len(timeline),
        "timeline": timeline
    }
    
    logger.info(f"Built timeline for object {object_id}: {len(timeline)} events")
    return report


def get_zone_activity() -> Dict[str, List[Dict[str, Any]]]:
    """
    Get all zones/locations and the objects that appeared in them with timestamps.
    
    Groups activity by zone, showing which objects were there and when.
    
    Returns:
        Dict where keys are zone names and values are lists of object appearances
    """
    logger.debug("Getting zone activity report")
    
    cypher = """
    MATCH (o:Object)-[r]->(zone:Value)
    WHERE type(r) IN [
        'POSITIONED_AT', 'NEAR', 'SURROUNDED_BY', 'ADJACENT_TO',
        'ON', 'INSIDE', 'STOPPED_AT', 'WAITING_AT', 'CROSSING',
        'IN_FRONT_OF', 'BEHIND', 'FACING'
    ]
    RETURN 
        zone.value AS zone,
        type(r) AS relation,
        o.id AS object_id,
        o.label AS label,
        r.timestamp AS timestamp,
        r.captured_at AS captured_at,
        r.target_entity_type AS entity_type
    ORDER BY zone.value, r.timestamp
    """
    
    with get_session() as session:
        result = session.run(cypher)
        records = [dict(record) for record in result]
    
    # Group by zone
    zones = {}
    for record in records:
        zone_name = record["zone"]
        if zone_name not in zones:
            zones[zone_name] = []
        
        zones[zone_name].append({
            "object_id": record["object_id"],
            "label": record["label"],
            "relation": record["relation"],
            "timestamp_sec": record["timestamp"],
            "captured_at": str(record["captured_at"]) if record["captured_at"] else None,
            "entity_type": record["entity_type"]
        })
    
    logger.info(f"Found {len(zones)} zones with activity")
    return zones