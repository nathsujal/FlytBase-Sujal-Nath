from ..connection import get_reader


def get_frame_path(frame_id: int) -> str:
    """Get frame path from database."""
    with get_reader() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT image_path
                FROM frames
                WHERE id = %s
            """, (frame_id,))
            return cursor.fetchone()[0]