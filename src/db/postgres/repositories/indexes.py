from ..connection import get_writer
from src.utils import get_logger

logger = get_logger(__name__)


def _index_frames():
    """Create indexes on frames table."""
    logger.info("Creating indexes on frames table...")
    
    with get_writer() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_frames_novel ON frames(is_novel)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_frames_timestamp ON frames(timestamp_sec)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_frames_captured_at ON frames(captured_at)")
    
    logger.info("Frames indexes created")


def _index_objects():
    """Create indexes on objects table."""
    logger.info("Creating indexes on objects table...")
    
    with get_writer() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_objects_label ON objects(label)")
    
    logger.info("Objects indexes created")


def _index_events():
    """Create indexes on events table."""
    logger.info("Creating indexes on events table...")
    
    with get_writer() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_events_object ON events(object_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_events_frame ON events(frame_id)")
            cur.execute("SELECT count(*) FROM events")
            num_rows = cur.fetchone()[0]
            num_lists = max(1, int(num_rows**0.5))
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_events_embedding
                ON events
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = {num_lists})
                """)
    logger.info("Events indexes created")


# Registry of index functions (must be after function definitions)
_indexes = {
    "frames": _index_frames,
    "objects": _index_objects,
    "events": _index_events
}


def index_table(table_name: str):
    """Index a specific table by name."""
    if table_name not in _indexes:
        raise ValueError(f"Invalid table name: {table_name}. Valid options: {list(_indexes.keys())}")
    _indexes[table_name]()