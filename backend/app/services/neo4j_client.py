import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")

class AegisGraphDatabase:
    def __init__(self):
        # Establish connection to the local Neo4j instance
        self.driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

    def close(self):
        self.driver.close()

    def record_transaction(self, sender: str, recipient: str, value: float, tx_hash: str):
        # EVERYTHING BELOW MUST BE INDENTED
        query = """
        MERGE (s:Wallet {address: $sender})
        MERGE (r:Wallet {address: $recipient})
        MERGE (s)-[t:TRANSFERRED_TO {hash: $tx_hash}]->(r)
        SET t.value = $value
        """

        with self.driver.session() as session:
            session.run(
                query,
                sender=sender,
                recipient=recipient,
                value=value,
                tx_hash=tx_hash
            )

# Instantiate a global client to be used by the workers
db = AegisGraphDatabase()