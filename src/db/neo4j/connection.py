from neo4j import GraphDatabase
from functools import lru_cache
from contextlib import contextmanager
from src.config.settings import settings
from src.utils import get_logger

logger = get_logger(__name__)


class Neo4jConnection:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password)
        )
        logger.info(f"Neo4j connected to {settings.neo4j_uri}")

    def close(self):
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")

    def session(self):
        return self.driver.session(database=settings.neo4j_database)


@lru_cache(maxsize=1)
def neo4j_client() -> Neo4jConnection:
    """Get singleton Neo4j connection."""
    return Neo4jConnection()


@contextmanager
def get_session():
    """Context manager for Neo4j session with auto-cleanup."""
    session = neo4j_client().session()
    try:
        yield session
    finally:
        session.close()