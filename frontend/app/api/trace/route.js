import { NextResponse } from 'next/server';
import { readQuery } from '@/app/lib/neo4j';
import neo4j from 'neo4j-driver';

export async function GET(request) {
  try {
    const { searchParams } = new URL(request.url);
    const address = searchParams.get('address');

    if (!address) {
      return NextResponse.json({ data: [], error: 'Address parameter is missing' }, { status: 400 });
    }

    // Dynamic label-free path tracing query
    const cypher = `
      MATCH path = (s {address: $address})-[*1..15]->(recipient)
      UNWIND relationships(path) AS rel
      WITH DISTINCT rel, startNode(rel) AS sender, endNode(rel) AS recipient
      RETURN
        sender.address     AS sender,
        sender.platform    AS senderPlatform,
        type(rel)          AS type,
        rel.hash           AS txHash,
        rel.value          AS value,
        rel.asset          AS asset,
        recipient.address  AS recipient,
        recipient.chain    AS targetChain,
        recipient.platform AS recipientPlatform,
        recipient.risk_score  AS riskScore,
        recipient.risk_level  AS riskLevel,
        recipient.risk_flags  AS riskFlags,
        recipient.vasp_tag    AS vaspTag
      ORDER BY id(rel) ASC
    `;

    let rawData;
    try {
      rawData = await readQuery(cypher, { address: address.toLowerCase().trim() });
    } catch (dbError) {
      console.error("❌ Neo4j Query Failure:", dbError);
      return NextResponse.json({ data: [], error: `Database query failed: ${dbError.message}` }, { status: 200 });
    }

    if (!rawData || !Array.isArray(rawData)) {
      return NextResponse.json({ data: [] });
    }

    // Safely parse numbers to prevent serialization exceptions
    const safeData = rawData.map(row => {
      let safeRow = { ...row };
      
      if (neo4j.isInt(row.value)) {
        safeRow.value = row.value.toNumber();
      } else if (typeof row.value === 'number') {
        safeRow.value = row.value;
      } else {
        safeRow.value = parseFloat(row.value) || 0;
      }

      if (neo4j.isInt(row.riskScore)) {
        safeRow.riskScore = row.riskScore.toNumber();
      }

      return safeRow;
    });

    return NextResponse.json({ data: safeData });

  } catch (globalError) {
    console.error("❌ Critical API Exception:", globalError);
    // Absolute fallback to ensure valid JSON is ALWAYS sent
    return NextResponse.json({ data: [], error: "Critical server execution fault encountered" }, { status: 200 });
  }
}