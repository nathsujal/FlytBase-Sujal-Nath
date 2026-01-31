from ..connection import get_session
from src.utils import get_logger

logger = get_logger(__name__)


def save_object(object_id: int, label: str):
    """Create or update an Object node."""
    logger.debug(f"Saving object {object_id} with label {label}")
    with get_session() as session:
        session.run("""
            MERGE (o:Object {id: $object_id})
            SET o.label = $label
            """, object_id=object_id, label=label)
    logger.debug(f"Object {object_id} saved successfully")


def link_attribute(object_id: int, attr_name: str, attr_value: str):
    """Link object to value with dynamic relationship name."""
    logger.debug(f"Linking attribute {attr_name} to object {object_id} with value {attr_value}")
    with get_session() as session:
        session.run(f"""
            MATCH (o:Object {{id: $object_id}})
            MERGE (v:Value {{value: $attr_value}})
            MERGE (o)-[:{attr_name}]->(v)
            """, object_id=object_id, attr_value=attr_value)
    logger.debug(f"Attribute {attr_name} linked successfully to object {object_id}")


def save_object_with_attributes(object_id: int, label: str, attributes: dict):
    """Create or update an Object node with attributes."""
    logger.debug(f"Saving Object {object_id} with attributes {attributes}")
    with get_session() as session:
        session.run("""
            MERGE (o:Object {id: $object_id})
            SET o.label = $label
            """, object_id=object_id, label=label)
        for attr_name, attr_value in attributes.items():
            session.run(f"""
                MATCH (o:Object {{id: $object_id}})
                MERGE (v:Value {{value: $attr_value}})
                MERGE (o)-[:{attr_name}]->(v)
                """, object_id=object_id, attr_value=str(attr_value))
    logger.debug(f"Object {object_id} with attributes saved successfully")