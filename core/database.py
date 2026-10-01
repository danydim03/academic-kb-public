import os
import logging
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)

class Neo4jManager:
    def __init__(self, uri, user, password, database="neo4j"):
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self.driver = None

    def connect(self):
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            self.driver.verify_connectivity()
            logger.info("Connected to Neo4j successfully.")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def close(self):
        if self.driver:
            self.driver.close()
            logger.info("Closed Neo4j connection.")

    def execute_query(self, query: str, parameters: dict = None):
        """Execute a query that does not require a return."""
        with self.driver.session(database=self.database) as session:
            return session.run(query, parameters or {}).data()

    def create_vector_index(self, index_name: str, label: str, property_name: str, dimensions: int):
        """Create a vector index for chunks."""
        query = f"""
        CREATE VECTOR INDEX {index_name} IF NOT EXISTS
        FOR (n:{label}) ON (n.{property_name})
        OPTIONS {{
          indexConfig: {{
            `vector.dimensions`: $dimensions,
            `vector.similarity_function`: 'cosine'
          }}
        }}
        """
        self.execute_query(query, {"dimensions": dimensions})
        logger.info(f"Vector index '{index_name}' created/verified.")

    def create_fulltext_index(self, index_name: str, labels: list, properties: list):
        """Create a fulltext index."""
        labels_str = "|".join(labels)
        props_str = ", ".join([f"n.{p}" for p in properties])
        query = f"""
        CREATE FULLTEXT INDEX {index_name} IF NOT EXISTS
        FOR (n:{labels_str}) ON EACH [{props_str}]
        """
        self.execute_query(query)
        logger.info(f"Full-text index '{index_name}' created/verified.")

    def ensure_constraints(self):
        constraints = [
            "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT concept_id IF NOT EXISTS FOR (c:Concept) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT source_id IF NOT EXISTS FOR (s:Source) REQUIRE s.id IS UNIQUE",
        ]
        for query in constraints:
            self.execute_query(query)
        logger.info("Database constraints verified.")
