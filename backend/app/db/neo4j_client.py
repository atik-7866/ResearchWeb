"""
Neo4j driver wrapper.

Graph model implemented here (Phase 1 subset - just the write path and
basic reads; richer traversal queries for citation chains, foundational
papers, etc. land in Phase 3):

    (:Paper {paper_id, title, abstract, year, doi, arxiv_id, venue, cited_by_count})
    (:Author {author_id, name})
    (:Topic {name})

    (:Paper)-[:AUTHORED_BY]->(:Author)
    (:Paper)-[:HAS_TOPIC]->(:Topic)
    (:Paper)-[:CITES]->(:Paper)
    (:Author)-[:WORKS_ON]->(:Topic)          (derived, see WORKS_ON note below)

Year is modeled as a Paper property (not a separate node) for Phase 1
simplicity; Phase 3 introduces a (:Year) node if timeline queries need it.
"""
from __future__ import annotations

from functools import lru_cache

from loguru import logger
from neo4j import GraphDatabase, Driver

from app.config import get_settings
from app.schemas.paper import NormalizedPaper

settings = get_settings()


class Neo4jClient:
    def __init__(self, uri: str, user: str, password: str, database: str) -> None:
        self._driver: Driver = GraphDatabase.driver(uri, auth=(user, password))
        self._database = database

    def close(self) -> None:
        self._driver.close()

    def verify_connectivity(self) -> bool:
        try:
            self._driver.verify_connectivity()
            return True
        except Exception as e:
            logger.error(f"Neo4j connectivity check failed: {e}")
            return False

    def ensure_constraints(self) -> None:
        """Idempotent schema setup. Safe to call on every startup."""
        statements = [
            "CREATE CONSTRAINT paper_id_unique IF NOT EXISTS FOR (p:Paper) REQUIRE p.paper_id IS UNIQUE",
            "CREATE CONSTRAINT author_id_unique IF NOT EXISTS FOR (a:Author) REQUIRE a.author_id IS UNIQUE",
            "CREATE CONSTRAINT topic_name_unique IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE",
        ]
        with self._driver.session(database=self._database) as session:
            for stmt in statements:
                session.run(stmt)
        logger.info("Neo4j constraints ensured")

    def upsert_paper(self, paper: NormalizedPaper) -> None:
        """
        Write one paper and its relationships (authors, topics).
        CITES edges are written in a second pass (upsert_citations) once
        all papers in a batch exist as nodes, so edges aren't dropped
        when a cited paper hasn't been ingested yet - it's created as a
        stub node and enriched later if it's ever ingested fully.
        """
        query = """
        MERGE (p:Paper {paper_id: $paper_id})
        SET p.title = $title,
            p.abstract = $abstract,
            p.year = $year,
            p.venue = $venue,
            p.doi = $doi,
            p.arxiv_id = $arxiv_id,
            p.cited_by_count = $cited_by_count,
            p.source = $source,
            p.stub = false

        WITH p
        UNWIND $authors AS author
            MERGE (a:Author {author_id: coalesce(author.openalex_id, author.name)})
            SET a.name = author.name
            MERGE (p)-[:AUTHORED_BY]->(a)

        WITH p
        UNWIND $topics AS topic_name
            MERGE (t:Topic {name: topic_name})
            MERGE (p)-[:HAS_TOPIC]->(t)
        """
        with self._driver.session(database=self._database) as session:
            session.run(
                query,
                paper_id=paper.paper_id,
                title=paper.title,
                abstract=paper.abstract,
                year=paper.year,
                venue=paper.venue,
                doi=paper.doi,
                arxiv_id=paper.arxiv_id,
                cited_by_count=paper.cited_by_count,
                source=paper.source,
                authors=[a.model_dump() for a in paper.authors],
                topics=paper.topics,
            )

        # Derived WORKS_ON edges: author works on the topics of papers they wrote.
        works_on_query = """
        MATCH (p:Paper {paper_id: $paper_id})-[:AUTHORED_BY]->(a:Author)
        MATCH (p)-[:HAS_TOPIC]->(t:Topic)
        MERGE (a)-[:WORKS_ON]->(t)
        """
        with self._driver.session(database=self._database) as session:
            session.run(works_on_query, paper_id=paper.paper_id)

    def upsert_citations(self, paper: NormalizedPaper) -> None:
        """
        Create CITES edges. If the cited paper hasn't been ingested yet,
        create a lightweight stub node for it (stub=true) so the edge
        isn't lost; if it's ingested later, upsert_paper fills it in
        and flips stub back to false.
        """
        if not paper.referenced_works:
            return
        query = """
        MATCH (p:Paper {paper_id: $paper_id})
        UNWIND $refs AS ref_id
            MERGE (cited:Paper {paper_id: ref_id})
            ON CREATE SET cited.stub = true
            MERGE (p)-[:CITES]->(cited)
        """
        with self._driver.session(database=self._database) as session:
            session.run(query, paper_id=paper.paper_id, refs=paper.referenced_works)

    def count_papers(self) -> int:
        with self._driver.session(database=self._database) as session:
            result = session.run("MATCH (p:Paper) WHERE p.stub = false OR p.stub IS NULL RETURN count(p) AS c")
            return result.single()["c"]

    def get_paper(self, paper_id: str) -> dict | None:
        query = """
        MATCH (p:Paper {paper_id: $paper_id})
        OPTIONAL MATCH (p)-[:AUTHORED_BY]->(a:Author)
        OPTIONAL MATCH (p)-[:HAS_TOPIC]->(t:Topic)
        RETURN p, collect(DISTINCT a.name) AS authors, collect(DISTINCT t.name) AS topics
        """
        with self._driver.session(database=self._database) as session:
            record = session.run(query, paper_id=paper_id).single()
            if not record:
                return None
            p = dict(record["p"])
            p["authors"] = record["authors"]
            p["topics"] = record["topics"]
            return p

    # ------------------------------------------------------------------
    # Phase 2: graph traversal queries
    # ------------------------------------------------------------------

    def find_related_papers(self, paper_id: str, limit: int = 10) -> list[dict]:
        """
        Papers related to `paper_id` through shared topics and/or shared
        authors, ranked by a simple weighted overlap score (shared authors
        count more than shared topics - co-authorship is a stronger signal
        than a shared keyword).

        Run as two separate queries and merged in Python rather than one
        combined Cypher query, because combining two OPTIONAL MATCH
        expansions with COUNT() in a single query multiplies rows across
        both patterns and produces wrong counts.
        """
        topic_query = """
        MATCH (p:Paper {paper_id: $paper_id})-[:HAS_TOPIC]->(t:Topic)<-[:HAS_TOPIC]-(other:Paper)
        WHERE other.paper_id <> $paper_id AND (other.stub IS NULL OR other.stub = false)
        RETURN other.paper_id AS paper_id, other.title AS title, other.year AS year,
               other.cited_by_count AS cited_by_count, count(DISTINCT t) AS shared_topics
        """
        author_query = """
        MATCH (p:Paper {paper_id: $paper_id})-[:AUTHORED_BY]->(a:Author)<-[:AUTHORED_BY]-(other:Paper)
        WHERE other.paper_id <> $paper_id AND (other.stub IS NULL OR other.stub = false)
        RETURN other.paper_id AS paper_id, other.title AS title, other.year AS year,
               other.cited_by_count AS cited_by_count, count(DISTINCT a) AS shared_authors
        """
        scores: dict[str, dict] = {}
        with self._driver.session(database=self._database) as session:
            for record in session.run(topic_query, paper_id=paper_id):
                pid = record["paper_id"]
                scores[pid] = {
                    "paper_id": pid,
                    "title": record["title"],
                    "year": record["year"],
                    "cited_by_count": record["cited_by_count"],
                    "shared_topics": record["shared_topics"],
                    "shared_authors": 0,
                }
            for record in session.run(author_query, paper_id=paper_id):
                pid = record["paper_id"]
                if pid not in scores:
                    scores[pid] = {
                        "paper_id": pid,
                        "title": record["title"],
                        "year": record["year"],
                        "cited_by_count": record["cited_by_count"],
                        "shared_topics": 0,
                        "shared_authors": 0,
                    }
                scores[pid]["shared_authors"] = record["shared_authors"]

        for entry in scores.values():
            entry["relatedness_score"] = entry["shared_topics"] * 1.0 + entry["shared_authors"] * 2.0

        ranked = sorted(scores.values(), key=lambda e: (e["relatedness_score"], e["cited_by_count"] or 0), reverse=True)
        return ranked[:limit]

    def find_citation_chain(self, paper_id: str, depth: int = 2, direction: str = "outgoing") -> list[dict]:
        """
        Traverse CITES edges up to `depth` hops using APOC (required because
        standard Cypher variable-length patterns don't accept a parameter
        for the hop bound). direction='outgoing' follows what this paper
        cites (older, foundational direction); 'incoming' follows what
        cites this paper (newer, influence direction).
        """
        depth = max(1, min(depth, 5))  # guard against runaway traversals
        rel_filter = "CITES>" if direction == "outgoing" else "<CITES"

        query = """
        MATCH (start:Paper {paper_id: $paper_id})
        CALL apoc.path.expandConfig(start, {
            relationshipFilter: $rel_filter,
            minLevel: 1,
            maxLevel: $depth,
            uniqueness: "NODE_GLOBAL"
        }) YIELD path
        WITH nodes(path) AS ns, length(path) AS hops
        RETURN [n IN ns WHERE (n.stub IS NULL OR n.stub = false) |
                {paper_id: n.paper_id, title: n.title, year: n.year, cited_by_count: n.cited_by_count}] AS chain,
               hops
        ORDER BY hops
        """
        with self._driver.session(database=self._database) as session:
            records = session.run(query, paper_id=paper_id, rel_filter=rel_filter, depth=depth)
            return [{"hops": r["hops"], "chain": r["chain"]} for r in records if r["chain"]]

    def find_citation_path(self, from_id: str, to_id: str, max_hops: int = 6) -> dict | None:
        """Shortest citation path between two papers, in either citation direction."""
        max_hops = max(1, min(int(max_hops), 8))  # int-cast + clamp: safe to interpolate below
        query = f"""
        MATCH (a:Paper {{paper_id: $from_id}}), (b:Paper {{paper_id: $to_id}})
        MATCH path = shortestPath((a)-[:CITES*1..{max_hops}]-(b))
        RETURN [n IN nodes(path) | {{paper_id: n.paper_id, title: n.title, year: n.year}}] AS chain,
               length(path) AS hops
        """
        with self._driver.session(database=self._database) as session:
            record = session.run(query, from_id=from_id, to_id=to_id).single()
            if not record:
                return None
            return {"chain": record["chain"], "hops": record["hops"]}

    def find_foundational_papers(self, topic: str, limit: int = 10) -> list[dict]:
        """
        Heuristic for "foundational": within a topic, prefer older papers
        with high citation counts. This is a proxy, not ground truth -
        the API layer should label it as such.
        """
        query = """
        MATCH (t:Topic {name: $topic})<-[:HAS_TOPIC]-(p:Paper)
        WHERE (p.stub IS NULL OR p.stub = false) AND p.cited_by_count IS NOT NULL
        RETURN p.paper_id AS paper_id, p.title AS title, p.year AS year,
               p.cited_by_count AS cited_by_count
        ORDER BY p.cited_by_count DESC, p.year ASC
        LIMIT $limit
        """
        with self._driver.session(database=self._database) as session:
            return [dict(r) for r in session.run(query, topic=topic, limit=limit)]

    def find_recent_papers(self, topic: str, limit: int = 10) -> list[dict]:
        query = """
        MATCH (t:Topic {name: $topic})<-[:HAS_TOPIC]-(p:Paper)
        WHERE (p.stub IS NULL OR p.stub = false) AND p.year IS NOT NULL
        RETURN p.paper_id AS paper_id, p.title AS title, p.year AS year,
               p.cited_by_count AS cited_by_count
        ORDER BY p.year DESC, p.cited_by_count DESC
        LIMIT $limit
        """
        with self._driver.session(database=self._database) as session:
            return [dict(r) for r in session.run(query, topic=topic, limit=limit)]

    def find_papers_between_topics(self, topic_a: str, topic_b: str, limit: int = 10) -> dict:
        """
        Two kinds of "between": papers explicitly tagged with both topics
        (direct overlap), and papers in one topic that cite/are cited by
        papers in the other (bridging via citation, not shared tagging).
        Useful now, and directly reusable by the Phase 9 gap finder.
        """
        direct_query = """
        MATCH (p:Paper)-[:HAS_TOPIC]->(:Topic {name: $topic_a})
        MATCH (p)-[:HAS_TOPIC]->(:Topic {name: $topic_b})
        WHERE p.stub IS NULL OR p.stub = false
        RETURN p.paper_id AS paper_id, p.title AS title, p.year AS year,
               p.cited_by_count AS cited_by_count
        ORDER BY p.cited_by_count DESC
        LIMIT $limit
        """
        bridge_query = """
        MATCH (pa:Paper)-[:HAS_TOPIC]->(:Topic {name: $topic_a})
        MATCH (pb:Paper)-[:HAS_TOPIC]->(:Topic {name: $topic_b})
        MATCH (pa)-[:CITES]-(pb)
        WHERE (pa.stub IS NULL OR pa.stub = false) AND (pb.stub IS NULL OR pb.stub = false)
        RETURN DISTINCT pa.paper_id AS a_id, pa.title AS a_title,
               pb.paper_id AS b_id, pb.title AS b_title
        LIMIT $limit
        """
        with self._driver.session(database=self._database) as session:
            direct = [dict(r) for r in session.run(direct_query, topic_a=topic_a, topic_b=topic_b, limit=limit)]
            bridges = [dict(r) for r in session.run(bridge_query, topic_a=topic_a, topic_b=topic_b, limit=limit)]
        return {"direct_overlap": direct, "citation_bridges": bridges}

    def get_author_profile(self, author_name: str) -> dict | None:
        query = """
        MATCH (a:Author) WHERE a.name = $name OR a.author_id = $name
        OPTIONAL MATCH (a)<-[:AUTHORED_BY]-(p:Paper) WHERE p.stub IS NULL OR p.stub = false
        OPTIONAL MATCH (a)-[:WORKS_ON]->(t:Topic)
        OPTIONAL MATCH (p)-[:AUTHORED_BY]->(coauthor:Author) WHERE coauthor <> a
        RETURN a.name AS name,
               collect(DISTINCT {paper_id: p.paper_id, title: p.title, year: p.year}) AS papers,
               collect(DISTINCT t.name) AS topics,
               collect(DISTINCT coauthor.name) AS coauthors
        """
        with self._driver.session(database=self._database) as session:
            record = session.run(query, name=author_name).single()
            if not record or record["name"] is None:
                return None
            return {
                "name": record["name"],
                "papers": [p for p in record["papers"] if p.get("paper_id")],
                "topics": [t for t in record["topics"] if t],
                "coauthors": [c for c in record["coauthors"] if c],
            }

    def list_topics(self, limit: int = 30) -> list[dict]:
        query = """
        MATCH (t:Topic)<-[:HAS_TOPIC]-(p:Paper)
        WHERE p.stub IS NULL OR p.stub = false
        RETURN t.name AS topic, count(p) AS paper_count
        ORDER BY paper_count DESC
        LIMIT $limit
        """
        with self._driver.session(database=self._database) as session:
            return [dict(r) for r in session.run(query, limit=limit)]

    def get_topic_papers(self, topic: str, limit: int = 20, sort: str = "citations") -> list[dict]:
        order_clause = {
            "citations": "p.cited_by_count DESC",
            "year": "p.year DESC",
            "oldest": "p.year ASC",
        }.get(sort, "p.cited_by_count DESC")

        query = f"""
        MATCH (t:Topic {{name: $topic}})<-[:HAS_TOPIC]-(p:Paper)
        WHERE p.stub IS NULL OR p.stub = false
        RETURN p.paper_id AS paper_id, p.title AS title, p.year AS year,
               p.cited_by_count AS cited_by_count
        ORDER BY {order_clause}
        LIMIT $limit
        """
        with self._driver.session(database=self._database) as session:
            return [dict(r) for r in session.run(query, topic=topic, limit=limit)]

    def get_topic_overview(self, topic: str) -> dict:
        """Paper-count-by-year and top authors for a topic - the building
        block the Phase 8 timeline feature will sit on top of."""
        by_year_query = """
        MATCH (t:Topic {name: $topic})<-[:HAS_TOPIC]-(p:Paper)
        WHERE p.year IS NOT NULL AND (p.stub IS NULL OR p.stub = false)
        RETURN p.year AS year, count(p) AS count
        ORDER BY year
        """
        top_authors_query = """
        MATCH (t:Topic {name: $topic})<-[:HAS_TOPIC]-(p:Paper)-[:AUTHORED_BY]->(a:Author)
        WHERE p.stub IS NULL OR p.stub = false
        RETURN a.name AS author, count(DISTINCT p) AS paper_count
        ORDER BY paper_count DESC
        LIMIT 10
        """
        with self._driver.session(database=self._database) as session:
            by_year = [dict(r) for r in session.run(by_year_query, topic=topic)]
            top_authors = [dict(r) for r in session.run(top_authors_query, topic=topic)]
        return {"topic": topic, "papers_by_year": by_year, "top_authors": top_authors}

    def get_citation_edges_among(self, paper_ids: list[str]) -> list[dict]:
        """
        Given a set of paper IDs (typically the top-K vector search hits),
        find which of them cite each other. This is the literal
        intersection point of vector and graph evidence in Hybrid RAG:
        "these papers are semantically similar AND some of them actually
        cite each other" is a much stronger signal than either fact alone.
        """
        if len(paper_ids) < 2:
            return []
        query = """
        MATCH (a:Paper)-[:CITES]->(b:Paper)
        WHERE a.paper_id IN $ids AND b.paper_id IN $ids
        RETURN a.paper_id AS citing_id, a.title AS citing_title,
               b.paper_id AS cited_id, b.title AS cited_title
        """
        with self._driver.session(database=self._database) as session:
            return [dict(r) for r in session.run(query, ids=paper_ids)]

    def get_citations(self, paper_id: str) -> dict:
        """Returns papers this paper cites, and papers that cite it."""
        query = """
        MATCH (p:Paper {paper_id: $paper_id})
        OPTIONAL MATCH (p)-[:CITES]->(cited:Paper)
        WHERE cited.stub IS NULL OR cited.stub = false
        WITH p, collect(DISTINCT {paper_id: cited.paper_id, title: cited.title, year: cited.year}) AS references
        OPTIONAL MATCH (citing:Paper)-[:CITES]->(p)
        RETURN references,
               collect(DISTINCT {paper_id: citing.paper_id, title: citing.title, year: citing.year}) AS cited_by
        """
        with self._driver.session(database=self._database) as session:
            record = session.run(query, paper_id=paper_id).single()
            if not record:
                return {"references": [], "cited_by": []}
            return {
                "references": [r for r in record["references"] if r.get("paper_id")],
                "cited_by": [r for r in record["cited_by"] if r.get("paper_id")],
            }


@lru_cache
def get_neo4j_client() -> Neo4jClient:
    return Neo4jClient(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
        database=settings.neo4j_database,
    )
