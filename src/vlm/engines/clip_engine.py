import clip
import torch
import numpy as np
from PIL import Image
from typing import List

from src.schemas import Frame
from src.config import settings
from src.utils import get_logger, retry

logger = get_logger(__name__)


class CLIPEngine:
    """CLIP model wrapper."""
    
    def __init__(
        self,
        batch_size: int = 8
    ):
        """
        Initialize CLIP engine.
        
        Args:
            batch_size: Batch size for processing multiple objects
        """
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        # Load CLIP model
        self.model, self.preprocess = clip.load(settings.clip_model, self.device)
        self.model.eval()

        # Get embedding dimension
        with torch.no_grad():
            dummy = torch.zeros(1, 3, 224, 224).to(self.device)
            self.embedding_dim = self.model.encode_image(dummy).shape[-1]

        # Batch config
        self.batch_size = batch_size

        logger.info(
            f"CLIPEngine initialized | Model: {settings.clip_model} | "
            f"Device: {self.device} | Dim: {self.embedding_dim}"
        )
    
    @retry(retries=3, delay=1.0, backoff=2.0)
    def encode_frame(self, frame: Frame) -> np.ndarray:
        """
        Encode frame to embedding.
        
        Args:
            frame: Frame to encode
        
        Returns:
            Embedding array (512-dim for ViT-B/32)
        """
        return self._compute_embedding(frame.image)
    
    @retry(retries=3, delay=1.0, backoff=2.0)
    def batch_encode_frames(self, frames: List[Frame]) -> np.ndarray | None:
        """
        Batch encode frames.
        
        Args:
            frames: List of frames to encode
        
        Returns:
            List of embeddings (one per frame)
        """
        if not frames:
            logger.debug("No frames to encode")
            return None
        
        return self._batch_compute(frames)
    
    def _compute_embedding(self, image: np.ndarray) -> np.ndarray:
        """Compute single embedding (internal)."""
        image_tensor = self.preprocess(
            Image.fromarray(image)
        ).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            embedding = self.model.encode_image(image_tensor)
            embedding = embedding / embedding.norm(dim=-1, keepdim=True)
        
        return embedding.cpu().numpy()[0]
    
    def _batch_compute(self, frames: List[Frame]) -> np.ndarray:
        """Batch compute embeddings with chunking for stability."""
        # Chunk large batches
        if len(frames) > self.batch_size:
            logger.debug(
                f"Chunking {len(frames)} frames into batches of {self.batch_size}"
            )
            chunks = []
            for i in range(0, len(frames), self.batch_size):
                chunk = frames[i:i + self.batch_size]
                chunk_embeddings = self._batch_compute(chunk)
                chunks.append(chunk_embeddings)
            return np.vstack(chunks)
        
        # Process batch
        images = [
            self.preprocess(Image.fromarray(f.image)) for f in frames
        ]
        
        batch_tensor = torch.stack(images).to(self.device)
        
        with torch.no_grad():
            embeddings = self.model.encode_image(batch_tensor)
            embeddings = embeddings / embeddings.norm(dim=-1, keepdim=True)
        
        return embeddings.cpu().numpy()
    
    @retry(retries=3, delay=1.0, backoff=2.0)
    def encode_text(self, text: str) -> np.ndarray:
        """
        Encode text to embedding.
        
        Args:
            text: Text string to encode
        
        Returns:
            Embedding array (512-dim for ViT-B/32)
        """
        # Tokenize text
        text_tokens = clip.tokenize([text]).to(self.device)
        
        with torch.no_grad():
            text_embedding = self.model.encode_text(text_tokens)
            text_embedding = text_embedding / text_embedding.norm(dim=-1, keepdim=True)
        
        return text_embedding.cpu().numpy()[0]
    
    @retry(retries=3, delay=1.0, backoff=2.0)
    def batch_encode_texts(self, texts: List[str]) -> np.ndarray:
        """
        Batch encode multiple texts.
        
        Args:
            texts: List of text strings to encode
        
        Returns:
            2D numpy array of embeddings (N x 512 for ViT-B/32)
        """
        if not texts:
            return np.array([])
        
        # Tokenize all texts
        text_tokens = clip.tokenize(texts).to(self.device)
        
        with torch.no_grad():
            text_embeddings = self.model.encode_text(text_tokens)
            text_embeddings = text_embeddings / text_embeddings.norm(dim=-1, keepdim=True)
        
        return text_embeddings.cpu().numpy()
    
    def text_image_similarity(self, text: str, image: np.ndarray) -> float:
        """
        Compute similarity between text and image.
        
        Args:
            text: Text description
            image: Image as numpy array (BGR)
        
        Returns:
            Cosine similarity score (0-1)
        """
        text_emb = self.encode_text(text)
        image_emb = self._compute_embedding(image)
        return self.cosine_similarity(text_emb, image_emb)

    @staticmethod
    def cosine_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Compute cosine similarity."""
        return float(np.dot(emb1, emb2))


# Single Instance
_clip_engine = None
def get_clip_engine():
    global _clip_engine
    if _clip_engine is None:
        _clip_engine = CLIPEngine()
    return _clip_engine