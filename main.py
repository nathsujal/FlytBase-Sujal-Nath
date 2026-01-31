import os
import subprocess
import argparse
from pathlib import Path

from src.utils import get_logger
from src.loaders import DroneFootageLoader
from src.perciever import Perciever
from src.db.postgres import init_schema as init_postgres
from src.db.neo4j import init_schema as init_neo4j
from src.db.postgres import save_frames, save_objects
from src.db.postgres import index_table
from src.vlm import FrameAnalyzer, ObjectAnalyzer
from src.security.agent import run_security_analysis
from src.agent import SecurityAgent


logger = get_logger(__name__)


def run_pipeline(source: str, detect_interval: int = 5):
    """Run the full perception pipeline."""
    
    # Step 1: Load footage
    logger.info("Step 1: Loading Footage")
    loader = DroneFootageLoader(source)
    logger.info(f"Loaded {len(loader)} frames")
    
    # Step 2: Run perception (detection + tracking)
    logger.info("Step 2: Running Perception Pipeline")
    perciever = Perciever(frames=loader.frames, detect_interval=detect_interval)
    perciever.process_all()
    
    logger.info(f"Processed {len(perciever.frames)} frames")
    logger.info(f"Tracked {len(perciever.objects)} unique objects")
    
    # Step 3: Store to database
    logger.info("Step 3: Storing to Database")
    save_frames(perciever.frames)
    save_objects(list(perciever.objects.values()))
    logger.info("Data saved to PostgreSQL")

    # Step 4: Run VLM
    logger.info("Step 4: Running VLM")
    frame_analyzer = FrameAnalyzer()
    object_analyzer = ObjectAnalyzer()
    frame_analyzer.process(perciever.frames)
    object_analyzer.process(perciever.objects.values(), perciever.frames)
    logger.info("VLM analysis complete")

    # Step 5: Run Security Analysis
    logger.info("Step 5: Running Security Analysis")
    tracks, threats = run_security_analysis()
    logger.info("Security analysis complete")

    SecurityAgent().run_interactive()


def setup_db():
    """Setup the Neo4j and Postgres Database."""
    init_postgres()
    init_neo4j()


def main():
    parser = argparse.ArgumentParser(description="FlytBase Drone Perception Pipeline")
    parser.add_argument(
        "--source", "-s",
        required=True,
        help="Path to video file or frames directory"
    )
    parser.add_argument(
        "--detect-interval", "-d",
        type=int,
        default=5,
        help="Run detection every N frames (default: 5)"
    )
    
    args = parser.parse_args()
    # setup_db()
    run_pipeline(args.source, args.detect_interval)


if __name__ == "__main__":
    main()
