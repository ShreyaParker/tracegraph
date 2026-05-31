import neo4j from 'neo4j-driver';

const uri = process.env.NEO4J_URI || 'bolt://localhost:7687';
const user = process.env.NEO4J_USER || 'neo4j';
const password = process.env.NEO4J_PASSWORD || 'password123';

const driver = neo4j.driver(uri, neo4j.auth.basic(user, password));

export async function readQuery(cypher, params = {}) {
  const session = driver.session({ database: 'neo4j' });
  try {
    const result = await session.run(cypher, params);
    return result.records.map(record => record.toObject());
  } finally {
    await session.close();
  }
}