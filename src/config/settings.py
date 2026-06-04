import os
from pathlib import Path
from pydantic import BaseModel, model_validator
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    """Application settings loaded from environment variables."""

    # Neo4j connection
    neo4j_uri: str = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "password")
    neo4j_database: str = os.getenv("NEO4J_DATABASE", "knowlegegraph")

    # PostgreSQL connection
    pg_host: str = os.getenv("PG_HOST", "localhost")
    pg_port: int = os.getenv("PG_PORT", 5432)

    pg_database_name: str = os.getenv("PG_DATABASE_NAME", "raven")

    pg_writer: str = os.getenv("PG_WRITER_USER", "writer")
    pg_writer_password: str = os.getenv("PG_WRITER_PASSWORD", "writer_password")

    pg_reader: str = os.getenv("PG_READER_USER", "reader")
    pg_reader_password: str = os.getenv("PG_READER_PASSWORD", "reader_password")

    # Database pool settings
    db_pool_size: int = 5
    db_pool_max_overflow: int = 10
    db_pool_timeout: int = 30

    # Database paths
    db_setup_script: str = os.getenv("DB_SETUP_SCRIPT", "db.sh")

    # BLIP models
    blip_caption_model: str = os.getenv("BLIP_CAPTION_MODEL", "Salesforce/blip-image-captioning-large")
    blip_vqa_model: str = os.getenv("BLIP_VQA_MODEL", "Salesforce/blip-vqa-base")

    # CLIP model
    clip_model: str = os.getenv("CLIP_MODEL", "ViT-B/32")

    # Embedding interval
    frame_embedding_interval: int = int(os.getenv("FRAME_EMBEDDING_INTERVAL", 10))
    # Novelty threshold
    frame_novelty_threshold: float = float(os.getenv("FRAME_NOVELTY_THRESHOLD", 0.7))
    
    # Image storage
    image_storage_path: str = "data/frames"

    @model_validator(mode="after")
    def ensure_directories_exist(self):
        Path(self.image_storage_path).mkdir(parents=True, exist_ok=True)
        return self
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

settings = get_settings()