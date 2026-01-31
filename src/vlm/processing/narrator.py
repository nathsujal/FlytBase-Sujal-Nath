import cv2
import numpy as np
from typing import List
from pydantic import BaseModel
from langchain_core.output_parsers import StrOutputParser

from src.schemas import Frame, Object
from ..prompts import PROMPT
from src.db.postgres import save_event 
from src.utils import get_logger
from .kg_extractor import get_kg_extractor

logger = get_logger(__name__)


class QuestionList(BaseModel):
    questions: List[str]


def describe_object_contextually(
    obj: Object,
    frames: List[Frame],
    llm: 'LLM',
    blip_engine: 'BLIPEngine'
):
    """
    Generate contextual caption for an object at sampled frames.
    """
    # Get frame IDs where object actually has bounding boxes
    available_frame_ids = sorted(obj.bounding_boxes.keys())
    
    if not available_frame_ids:
        logger.debug(f"No bounding boxes for object {obj.object_id}")
        return

    kg_extractor = get_kg_extractor()
    
    # Sample evenly from available frames (max 10)
    num_samples = min(10, len(available_frame_ids))
    indices = np.linspace(0, len(available_frame_ids) - 1, num=num_samples, dtype=int)
    sampled_frame_ids = [available_frame_ids[i] for i in np.unique(indices)]

    logger.debug(f"Generating contextual captions for object {obj.object_id} | {', '.join(map(str, sampled_frame_ids))} frames")
    for frame_id in sampled_frame_ids:
        frame = next((f for f in frames if f.frame_id == frame_id), None)
        if frame is None:
            logger.warning(f"Frame {frame_id} not found")
            continue

        # 0. Prepare image
        combined_image = _prepare_image(frame, obj)
        if combined_image is None:
            logger.warning(f"Skipping frame {frame_id} for object {obj.object_id}: invalid crop")
            continue

        # 1. Generate questions
        questions = _generate_contextual_questions(obj.label, llm)

        # 2. Ask BLIP
        qa_pairs = _ask_contextual_questions(
            combined_image,
            questions,
            blip_engine
        )

        # 3. Synthesize final caption
        caption = _synthesize_caption(
            obj.label,
            qa_pairs,
            llm
        )

        # 4. Store caption
        save_event(
            object_id=obj.object_id,
            frame_id=int(frame_id),
            event_description=caption
        )

        # 5. Extract and store knowledge graph
        kg_extractor.extract_and_store(
            object_id=obj.object_id,
            object_label=obj.label,
            description=caption,
            timestamp=frame.timestamp_sec,
            captured_at=str(frame.captured_at)
        )

def _prepare_image(frame: Frame, obj: Object) -> np.ndarray:
    """
    Stack original frame and cropped object side by side.
    Prepare image for BLIP by cropping the object, padding to match height,
    and stacking horizontally with the original frame.
    ┌─────────────────┬──────────────┐
    │                 │              │
    │  Original Frame │ Cropped Obj  │
    │                 │  (padded)    │
    │                 │              │
    └─────────────────┴──────────────┘
    
    Args:
        frame: Frame containing the object
        obj: Object with bounding box info
        
    Returns:
        Combined image (original | padded crop), or None if crop is invalid
    """
    bbox = obj.bounding_boxes[frame.frame_id]
    x1, y1, x2, y2 = bbox.to_list()
    
    # Validate bounding box
    if x2 <= x1 or y2 <= y1:
        logger.warning(f"Invalid bounding box for object {obj.object_id}: ({x1},{y1},{x2},{y2})")
        return None
    
    crop = frame.image[y1:y2, x1:x2]
    
    # Validate crop is not empty
    if crop.size == 0 or crop.shape[0] == 0 or crop.shape[1] == 0:
        logger.warning(f"Empty crop for object {obj.object_id}")
        return None
    
    # Resize crop to match frame height
    target_h = frame.image.shape[0]
    scale = target_h / crop.shape[0]
    crop_resized = cv2.resize(crop, None, fx=scale, fy=scale)
    
    return np.hstack([frame.image, crop_resized])


def _generate_contextual_questions(obj_label: str, llm: 'LLM') -> List[str]:
    """
    Generate VQA questions to extract object's spatial context.

    Args:
        obj_label: Object label
        llm: LLM instance for question generation

    Returns:
        List of 3 contextual questions
    """
    prompt = f"The object is '{obj_label}'. "
    response = llm.invoke_structured(
        prompt=prompt,
        system_message=PROMPT.BOUNDED_OBJECT_CONTEXT_PROMPT,
        schema=QuestionList
    )
    questions = response.questions
    return questions


def _ask_contextual_questions(combined_image: np.ndarray, questions: List[str], blip_engine: 'BLIPEngine') -> List[str]:
    """
    Ask BLIP multiple contextual questions about an object.

    Args:
        combined_image: Image with object cropped and padded
        question: List of questions
        blip_engine: BLIPEngine instance

    Returns:
        List of answers
    """
    answers = []
    for question in questions:
        answer = blip_engine.answer_question(
            image=combined_image,
            question=question
        )
        answers.append(
            f"Question: {question}\nAnswer: {answer}"
        )
    
    return answers
    

def _synthesize_caption(
    obj_label: str,
    qa_pairs: List[str],
    llm: 'LLM'
) -> str:
    """
    Synthesize final caption for an object.

    Args:
        obj_label: Object label
        qa_pairs: List of QA pairs
        llm: LLM instance for caption synthesis

    Returns:
        Final caption
    """
    prompt = f"The object is '{obj_label}'. "

    caption = llm.invoke(
        system_message=PROMPT.CONTEXTUAL_DESCRIPTION_PROMPT,
        prompt=(
            f"The object is '{obj_label}'.\n"
            f"Contextual captions: {chr(10).join(qa_pairs)}."
        ),
        parser=StrOutputParser()
    )

    return caption