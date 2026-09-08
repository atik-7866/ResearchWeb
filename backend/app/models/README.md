This directory is reserved for ORM-style domain models if a relational
DB is introduced later (e.g. for user accounts / personal library
metadata in Phase 10). For Phase 1, Neo4j nodes/relationships (see
app/db/neo4j_client.py) and the Pydantic schemas in app/schemas/ are
the source of truth for data shape - no separate model layer needed yet.
