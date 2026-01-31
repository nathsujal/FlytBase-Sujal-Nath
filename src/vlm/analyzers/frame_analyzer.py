import numpy as np
from typing import List, TYPE_CHECKING

from src.config.settings import settings
from ..processing import profiler
from src.schemas import Frame
from ..engines.blip_engine import get_blip_engine
from ..engines.clip_engine import get_clip_engine
from src.llms.ollama import OllamaLLM
from src.db.neo4j import save_novel_frames
from src.utils import get_logger

logger = get_logger(__name__)


class FrameAnalyzer:
    def __init__(self):
        self.llm = OllamaLLM("qwen")
        self.blip_engine = get_blip_engine()
        self.clip_engine = get_clip_engine()

        self.embedding_interval = settings.frame_embedding_interval
        self.novelty_threshold = settings.frame_novelty_threshold

        logger.info(
            "FrameAnalyzer Initialized | "
            f"Embedding interval: {self.embedding_interval} | "
            f"Novelty threshold: {self.novelty_threshold}"
        )


    def process(self, frames: List[Frame]):
        """
        Process frames.

        Pipeline:
        1. Filter frames for embeddings (every N frames)
        2. Generate embeddings for target frames
        3. Check novelty against previous frames
        4. Describe novel frames with BLIP captions
        5. Generate scene attributes for novel frames
        6. Update novel frames in database
        """

        if not frames:
            logger.warning("No frames to process")
            return

        # 1. Filter frames for embedding (every N frames)
        target_frames = [
            f for f in frames
            if f.frame_id % self.embedding_interval == 0
        ]

        if not target_frames:
            logger.debug("No frames to process in this batch")
            return

        # 2. Generate embeddings for the target frames
        embeddings = self.clip_engine.batch_encode_frames(target_frames)

        if embeddings is None:
            logger.warning("No embeddings generated")
            return
        
        # 3. Check novelty
        novel_frames = self._get_novel_frames(
            embeddings=embeddings,
            frames=target_frames,
            novelty_threshold=self.novelty_threshold
        )

        # 4. Batch describe novel frames only
        if novel_frames:
            novel_frames = self._describe_scenes(frames=novel_frames)
        
        # 5. Generate scene attributes for novel frames
        if novel_frames:
            for frame in novel_frames:
                attributes = profiler.generate_scene_attributes(
                    frame_id=frame.frame_id,
                    frame_description=frame.caption,
                    frame_image=frame.image,
                    llm=self.llm,
                    blip_engine=self.blip_engine
                )

                frame.attributes = attributes

        # 6. Save novel frames
        save_novel_frames(novel_frames)

    
    def _get_novel_frames(
        self,
        embeddings: np.ndarray,
        frames: List[Frame],
        novelty_threshold: float = settings.frame_novelty_threshold
    ) -> List[Frame]:
        """
        Batch check novelty of frames.
        
        Args:
            embeddings: Array of embeddings
            frame_ids: List of frame ids to check novelty for
            novelty_threshold: Threshold for novelty check
        
        Returns:
            List of booleans indicating novelty of each frame
        """
        if embeddings is None or not frames:
            logger.warning("No embeddings or frames provided")
            return []
        
        # Ensure correct shape and contigous array
        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)
        
        embeddings_array = np.ascontiguousarray(embeddings.astype(np.float32))

        results = []
        for i, frame in enumerate(frames):
            frame_emb = embeddings_array[i]

            # First frame is always novel
            if i == 0:
                results.append(True)
                continue

            # Check against all previous frames
            novelty_scores = np.dot(frame_emb, embeddings_array[:i].T)
            novelty_scores = np.abs(novelty_scores)
            novelty_scores = novelty_scores > novelty_threshold
            is_novel = not novelty_scores.any()
            results.append(is_novel)

        return [f for f, is_novel in zip(frames, results) if is_novel]

    def _describe_scenes(
        self,
        frames: List[Frame]
    ) -> List[Frame]:
        """
        Batch generate captions for multiple frames.
    
        Args:
            frames: List of frames to describe
            blip_engine: BLIPEngine instance
            max_length: Maximum caption length
        
        Returns:
            List of frames with captions
        """
        if not frames:
            return []
        
        captions = self.blip_engine.batch_caption_image(
            images=[frame.image for frame in frames],
            max_length=200,
            num_beams=3
        )
        
        # Validate
        if not captions or any(not c.strip() for c in captions):
            raise ValueError("Empty captions in batch")
        
        # Update frames
        for frame, caption in zip(frames, captions):
            frame.caption = caption
        
        logger.info(f"Batch described {len(frames)} frames")
        return frames