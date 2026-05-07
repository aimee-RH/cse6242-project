"""
Session-level routing state persistence.

Stores resolved_entities and pending_clarification on the Neo4j Session node,
so that routing state survives across HTTP requests.

Author: Scholar Compass Team
Date: 2025-04-22 (Step 4C)
"""
import json
import logging
from typing import Dict, Optional, Any
from tools.neo4j_connector import neo4j_connector
from graph.schemas import ResolvedAuthor, PendingClarification

logger = logging.getLogger(__name__)


def load_routing_state(session_id: str) -> Dict[str, Any]:
    """
    Load resolved_entities and pending_clarification from Neo4j Session node.

    Args:
        session_id: The session identifier

    Returns:
        {
            "resolved_entities": Dict[str, ResolvedAuthor],
            "pending_clarification": Optional[PendingClarification],
        }
    """
    query = """
    MATCH (s:Session {session_id: $session_id})
    RETURN s.routing_resolved_entities_json AS entities_json,
           s.routing_pending_clarification_json AS pending_json
    """

    result = neo4j_connector.execute_query(query, {"session_id": session_id})

    if not result:
        logger.info(f"[session_store] No existing session {session_id}, returning empty state")
        return {"resolved_entities": {}, "pending_clarification": None}

    record = result[0]

    # Parse resolved_entities
    resolved_entities = {}
    if record.get("entities_json"):
        try:
            raw = json.loads(record["entities_json"])
            resolved_entities = {
                name: ResolvedAuthor.model_validate(data)
                for name, data in raw.items()
            }
        except Exception as e:
            logger.warning(f"[session_store] Failed to parse resolved_entities: {e}")

    # Parse pending_clarification
    pending = None
    if record.get("pending_json"):
        try:
            pending = PendingClarification.model_validate_json(record["pending_json"])
        except Exception as e:
            logger.warning(f"[session_store] Failed to parse pending_clarification: {e}")

    logger.info(
        f"[session_store] Loaded session {session_id}: "
        f"{len(resolved_entities)} entities, pending={'yes' if pending else 'no'}"
    )
    return {
        "resolved_entities": resolved_entities,
        "pending_clarification": pending,
    }


def save_routing_state(
    session_id: str,
    resolved_entities: Dict[str, ResolvedAuthor],
    pending_clarification: Optional[PendingClarification],
) -> None:
    """
    Save routing state to Neo4j Session node.
    Uses MERGE to handle both new sessions and updates.

    Args:
        session_id: The session identifier
        resolved_entities: Dict of author name to ResolvedAuthor
        pending_clarification: Optional PendingClarification
    """
    # Serialize to JSON strings (Neo4j properties can be strings)
    entities_json = json.dumps({
        name: author.model_dump() for name, author in resolved_entities.items()
    }, ensure_ascii=False) if resolved_entities else None

    pending_json = pending_clarification.model_dump_json() if pending_clarification else None

    query = """
    MERGE (s:Session {session_id: $session_id})
    SET s.routing_resolved_entities_json = $entities_json,
        s.routing_pending_clarification_json = $pending_json,
        s.routing_updated_at = datetime()
    """

    neo4j_connector.execute_query(
        query,
        {
            "session_id": session_id,
            "entities_json": entities_json,
            "pending_json": pending_json,
        }
    )

    logger.info(
        f"[session_store] Saved session {session_id}: "
        f"{len(resolved_entities)} entities, pending={'yes' if pending_clarification else 'no'}"
    )


def ensure_session_constraint():
    """
    Ensure the session_id uniqueness constraint exists.

    Run this once during initialization to ensure data integrity.
    """
    query = """
    CREATE CONSTRAINT session_id_unique IF NOT EXISTS
    FOR (s:Session) REQUIRE s.session_id IS UNIQUE
    """
    try:
        neo4j_connector.execute_query(query)
        logger.info("[session_store] Ensured session_id uniqueness constraint")
    except Exception as e:
        logger.warning(f"[session_store] Failed to create constraint: {e}")


# Auto-create constraint on module import
try:
    ensure_session_constraint()
except Exception as e:
    logger.warning(f"[session_store] Could not create constraint on import: {e}")
