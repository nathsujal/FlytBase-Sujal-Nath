from ..connection import get_session
from src.utils import get_logger

logger = get_logger(__name__)


def find_by_attribute(attr_name: str, attr_value: str) -> list:
    """Find objects by attribute."""
    logger.debug(f"Finding objects by attribute {attr_name} with value {attr_value}")
    with get_session() as session:
        result = session.run(f"""
            MATCH (o:Object)-[:{attr_name}]->(v:Value {{value: $attr_value}})
            RETURN o.id, o.label
            """, attr_value=attr_value)
        objects = [{"id": r["o.id"], "label": r["o.label"]} for r in result]
    logger.debug(f"Found {len(objects)} objects")
    return objects


def get_object_attrs(object_id: int) -> dict:
    """Get attributes of an object."""
    logger.debug(f"Getting attributes for object {object_id}")
    with get_session() as session:
        result = session.run("""
            MATCH (o:Object {id: $object_id})-[r]->(v:Value)
            RETURN type(r) AS name, v.value AS value
            """, object_id=object_id)
        attrs = {r["name"]: r["value"] for r in result}
    logger.debug(f"Found {len(attrs)} attributes")
    return attrs