from .connection import get_session
from src.utils import get_logger

logger = get_logger(__name__)


def truncate_database():
    """Delete all nodes and relationships in Neo4j."""
    logger.info("Truncating Neo4j database...")
    
    with get_session() as session:
        # Delete all nodes and relationships
        session.run("MATCH (n) DETACH DELETE n")
    
    logger.info("Neo4j database truncated")


def init_schema():
    """Initialize Neo4j schema with constraints.
    
    Truncates the database first to ensure a clean slate.
    """
    # Clean database first
    truncate_database()
    
    logger.info("Initializing Neo4j schema...")
    
    with get_session() as session:
        session.run("""
            CREATE CONSTRAINT object_id IF NOT EXISTS
            FOR (o:Object) REQUIRE o.id IS UNIQUE
        """)

        session.run("""
            CREATE CONSTRAINT frame_id IF NOT EXISTS
            FOR (f:NovelFrame) REQUIRE f.id IS UNIQUE
        """)
    
    logger.info("Neo4j schema initialized")
