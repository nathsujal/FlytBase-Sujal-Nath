from typing import List

from src.schemas import Frame
from ..connection import get_session
from src.utils import get_logger


logger = get_logger(__name__)


def save_novel_frames(frames: List[Frame]):
    """Save novel frames with their captions and attributes to Neo4j."""
    if not frames:
        logger.warning("No frames to save")
        return

    logger.debug(f"Saving {len(frames)} novel frames")

    with get_session() as session:
        for frame in frames:
            # Create frame node with caption
            session.run("""
                MERGE (f:NovelFrame {id: $frame_id})
                SET f.caption = $caption
            """, frame_id=frame.frame_id, caption=frame.caption)

            # Link attributes
            for attr_name, attr_value in frame.attributes.items():
                session.run(f"""
                    MATCH (f:NovelFrame {{id: $frame_id}})
                    MERGE (v:Value {{value: $attr_value}})
                    MERGE (f)-[:{attr_name}]->(v)
                """, frame_id=frame.frame_id, attr_value=str(attr_value))

    logger.info(f"Saved {len(frames)} novel frames")