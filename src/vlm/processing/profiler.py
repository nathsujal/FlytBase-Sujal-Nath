import numpy as np
from pydantic import BaseModel
from typing import Tuple, Dict, Optional, Literal, List
from langchain_core.output_parsers import StrOutputParser

from ..prompts import PROMPT
from src.db.neo4j import save_object_with_attributes
from src.schemas import Object, Frame, BoundingBox
from src.utils import get_logger

logger = get_logger(__name__)


class Attribute(BaseModel):
    type: Literal["string", "boolean", "number", "enum", "list[string]"] = "string"
    description: str = ""
    values: Optional[List[str]] = None

class AttributeSchema(BaseModel):
    """Schema for attributes returned by LLM."""
    attributes: Dict[str, Attribute] = {}


def generate_scene_attributes(
    frame_id: int,
    frame_description: str,
    frame_image: np.ndarray,
    llm: 'LLM',
    blip_engine: 'BLIPEngine'
) -> Dict[str, str]:
    """
    Generate attribute schema for a scene description.

    Args:
        description: Scene description
        llm: LLM instance
    
    Returns:
        AttributeSchema with validated attributes
    """
    logger.debug(f"Generating scene attributes for frame {frame_id}")
    
    try:
        schema_response: AttributeSchema = llm.invoke_structured(
            prompt=f"Analyze this scene and generate security attributes:\n\n{frame_description}",
            system_message=PROMPT.SCENE_ATTRIBUTE_SCHEMA_PROMPT,
            schema=AttributeSchema
        )

        attribute_schema = schema_response.attributes
        logger.debug(f"Generated {len(attribute_schema)} attribute definitions for frame {frame_id}")

        attribute_values: Dict[str, str] = _interrogate_visual_attributes(
            image=frame_image,
            attributes=attribute_schema,
            llm=llm,
            blip_engine=blip_engine
        )

        logger.info(f"Saved {len(attribute_values)} scene attributes for frame {frame_id}")
        return attribute_values
        
    except Exception as e:
        logger.error(f"Failed to generate scene attributes for frame {frame_id}: {e}")
        raise


def generate_object_attributes(
    obj_id: int,
    obj_label: str,
    obj_bbox: BoundingBox,
    frame_image: np.ndarray,
    llm: 'LLM',
    blip_engine: 'BLIPEngine'
) -> Dict[str, str]:
    """
    Generate attribute schema for an object label.

    Args:
        label: Object label
        llm: LLM instance
    
    Returns:
        AttributeSchema with validated attributes
    """
    logger.debug(f"Generating object attributes for object {obj_id} ({obj_label})")
    
    try:
        schema_response: AttributeSchema = llm.invoke_structured(
            prompt=f"Analyze this object and generate security attributes:\n\n{obj_label}",
            system_message=PROMPT.OBJECT_ATTRIBUTE_SCHEMA_PROMPT,
            schema=AttributeSchema
        )

        attribute_schema = schema_response.attributes
        logger.debug(f"Generated {len(attribute_schema)} attribute definitions for object {obj_id}")

        attribute_values: Dict[str, str] = _interrogate_visual_attributes(
            image=frame_image,
            attributes=attribute_schema,
            llm=llm,
            blip_engine=blip_engine,
            obj_bbox=obj_bbox
        )

        save_object_with_attributes(obj_id, obj_label, attribute_values)
        logger.info(f"Saved {len(attribute_values)} object attributes for object {obj_id}")
        return attribute_values
        
    except Exception as e:
        logger.error(f"Failed to generate object attributes for object {obj_id}: {e}")
        raise


def _interrogate_visual_attributes(
    image: np.ndarray,
    attributes: Dict[str, Attribute],
    llm: 'LLM',
    blip_engine: 'BLIPEngine',
    obj_bbox: Optional[BoundingBox] = None
) -> Dict[str, str]:
    """
    Interrogate visual attributes for an object in an image.

    Args:
        image: Input image
        attributes: Attribute schema
        llm: LLM instance
        blip_engine: BLIP engine instance
        obj_bbox: Optional object bounding box
    
    Returns:
        Dictionary of attribute values
    """
    if not attributes:
        logger.debug("No attributes to interrogate")
        return {}
    
    logger.debug(f"Interrogating {len(attributes)} visual attributes")
    attributes_dict = {}
    
    for attr_name, attr_data in attributes.items():
        try:
            # Build prompt with optional fields
            prompt_parts = [
                "Generate a question for this attribute:",
                f"Name: {attr_name}",
                f"Description: {attr_data.description}"
            ]
            if attr_data.values:
                prompt_parts.append(f"Values: {attr_data.values}")
            if attr_data.type:
                prompt_parts.append(f"Type: {attr_data.type}")
            prompt = "\n".join(prompt_parts)

            question = llm.invoke(
                prompt,
                system_message=PROMPT.ATTRIBUTES_QUESTIONS_PROMPT,
                parser=StrOutputParser()
            )

            # Handle bbox - only pass if present
            bbox_list = obj_bbox.to_list() if obj_bbox else None
            answer = blip_engine.answer_question(
                image=image,
                question=question,
                bbox=bbox_list
            )

            attributes_dict[attr_name] = answer
            logger.debug(f"Attribute '{attr_name}': {answer}")
            
        except Exception as e:
            logger.warning(f"Failed to interrogate attribute '{attr_name}': {e}")
            attributes_dict[attr_name] = "unknown"
    
    return attributes_dict