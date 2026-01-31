import cv2
import numpy as np
from typing import List, Dict, TYPE_CHECKING

from ..processing import narrator, profiler
from src.schemas import Object, Frame
from src.llms.ollama import OllamaLLM
from ..engines.blip_engine import get_blip_engine
from src.db.postgres import get_frame_path
from src.utils import get_logger

logger = get_logger(__name__)


class ObjectAnalyzer:
    def __init__(self):
        self.llm = OllamaLLM("qwen")
        self.blip_engine = get_blip_engine()

        logger.info("ObjectAnalyzer initialized")

    def process(self, objects: List[Object], frames: List[Frame]):
        """
        Process objects.

        """
        if not objects:
            logger.warning("No objects to process")
            return

        logger.info(f"Analyzing {len(objects)} objects")

        for idx, obj in enumerate(objects):
            logger.debug(f"[{idx+1}/{len(objects)}] Analyzing object: {obj.object_id} | {obj.label}")

            # 1. Generate object attributes
            try:
                first_frame_id = obj.first_frame_id
                logger.debug(f"For object {obj.object_id} ({obj.label}), first frame id: {first_frame_id}")
                frame_path = get_frame_path(first_frame_id)

                if not frame_path:
                    logger.warning(f"No frame path for object {obj.object_id} ({obj.label})")
                    continue

                first_frame = cv2.imread(frame_path)
                if first_frame is None:
                    logger.warning(f"Failed to read frame: {frame_path}")
                    continue

                first_frame_rgb = cv2.cvtColor(first_frame, cv2.COLOR_BGR2RGB)
                
                attributes: Dict[str, str] = profiler.generate_object_attributes(
                    obj_id=obj.object_id,
                    obj_label=obj.label,
                    obj_bbox=obj.bounding_boxes[first_frame_id],
                    frame_image=first_frame_rgb,
                    llm=self.llm,
                    blip_engine=self.blip_engine
                )
            except Exception as e:
                logger.error(f"Failed to generate attributes for object {obj.object_id}: {e}")
                continue
            
            # 2. Generate contextual captions at sampled frames
            try:
                narrator.describe_object_contextually(obj, frames, self.llm, self.blip_engine)
            except Exception as e:
                logger.error(f"Failed to generate contextual captions for object {obj.object_id}: {e}")
                continue
