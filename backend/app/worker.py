import os
import asyncio
import ssl
import redis
import numpy as np
import xgboost as xgb
from dotenv import load_dotenv

# 1. Load environment variables FIRST
load_dotenv()

# 2. Import application services
from app.services.risk_scorer import (
    compute_risk_score,
    build_vasp_lookup
)
from app.services.alchemy import (
    fetch_outbound_transfers,
    fetch_transaction_input,
    scan_for_cross_chain_payload
)
from app.services.mempool import fetch_btc_greedy_path
from app.services.neo4j_client import db
from app.services.thorchain_resolver import resolve_thorchain_btc_output

# =========================================================
# THREAT INTELLIGENCE: ENTITY DATABASE
# =========================================================
ENTITY_DB = {
    # Centralised exchanges
    "binance":    {"type": "CEX",          "risk": 60, "note": "KYC available via law enforcement portal"},
    "okx":        {"type": "CEX",          "risk": 60, "note": "Law enforcement portal: law@okx.com"},
    "kraken":     {"type": "CEX",          "risk": 50, "note": "US subpoena process"},
    "coinbase":   {"type": "CEX",          "risk": 40, "note": "Highly cooperative — law@coinbase.com"},
    "paribu":     {"type": "CEX",          "risk": 55, "note": "Turkish exchange — local LE contact required"},
    # Swap services & Bridges
    "changenow":  {"type": "SWAP_SERVICE", "risk": 70, "note": "Provides IP logs — compliance@changenow.io"},
    "fixedfloat": {"type": "SWAP_SERVICE", "risk": 70, "note": "Non-custodial, has IP log data"},
    "allbridge":  {"type": "BRIDGE",       "risk": 75, "note": "Provided user IP in Zoth investigation"},
    "thorchain":  {"type": "BRIDGE",       "risk": 80, "note": "Decentralised ETH->BTC bridge, no central operator"},
    # High-risk & Cybercrime
    "tornado":    {"type": "MIXER",        "risk": 95, "note": "OFAC sanctioned. Notify FIU immediately."},
    "bitrefill":  {"type": "GIFT_CARD",    "risk": 80, "note": "Gift cards — provided IPs in Crystal investigations"},
    "roobet":     {"type": "GAMBLING",     "risk": 75, "note": "Offshore crypto casino, has user data"},
}

def resolve_entity(vasp_tag_from_api):
    """Matches a VASP tag from Alchemy/Blockstream to the internal Entity DB."""
    if not vasp_tag_from_api:
        return None
    tag_lower = str(vasp_tag_from_api).lower()
    for known_entity, data in ENTITY_DB.items():
        if known_entity in tag_lower:
            return {"name": vasp_tag_from_api, **data}
    return None

# =========================================================
# REDIS SETUP (Still used for loop prevention)
# =========================================================
redis_url = os.getenv("REDIS_URL", "")
clean_redis_url = redis_url.split("?")[0]

redis_client = redis.Redis.from_url(
    clean_redis_url,
    ssl_cert_reqs=ssl.CERT_NONE
)

THRESHOLD = float(os.getenv("VALUE_THRESHOLD", 0.1))

# =========================================================
# LOAD ML MODEL
# =========================================================
try:
    ml_pruner = xgb.XGBClassifier()
    ml_pruner.load_model("aegis_brain.json")
    print("🧠 TraceGraph Kaggle-Trained ML Brain Loaded.")
except Exception as e:
    print(f"⚠️ ML Model not found. Run train_ml.py first! Error: {e}")

# =========================================================
# MAIN TRACE TASK (Now 100% Async and Native)
# =========================================================

async def trace_wallet_task(
    wallet_address: str,
    chain: str = "ethereum",
    current_depth: int = 0,
    max_depth: int = 8
):
    wallet_address = wallet_address.lower()

    # LOOP PREVENTION
    if redis_client.sismember("tracegraph:autonomous_run", wallet_address):
        print(f"♻️ [SKIP] Loop prevented: {wallet_address}")
        return

    redis_client.sadd("tracegraph:autonomous_run", wallet_address)

    if current_depth >= max_depth:
        return

    print(f"\n[{chain.upper()} TRACE] Layer {current_depth}: {wallet_address}")

    # =====================================================
    # BITCOIN TRACE LOGIC
    # =====================================================
    if chain.lower() == "bitcoin":
        btc_data = await fetch_btc_greedy_path(wallet_address)
        if not btc_data:
            return

        tx_hash = btc_data["tx_hash"]
        peel_count = len(btc_data["all_peels"])
        print(f"\n🔍 [BTC BRANCHING] {peel_count} outputs detected.")

        if peel_count > 5:
            print(f"🛑 [MASS PAYOUT] Potential exchange/mixer detected.")
            db.driver.execute_query(
                "MERGE (w:CrossChainWallet {address: $addr}) SET w:ExchangeNode, w.classification = 'Institutional Batch Distributor', w.chain = 'Bitcoin'",
                addr=wallet_address
            )
            return

        for peel in btc_data["all_peels"]:
            peel_addr = peel["address"].lower()
            peel_val = peel["value"]

            is_exchange = peel_addr.startswith("bc1p") or len(peel_addr) > 50
            entity_tag = "Institutional Aggregator Hub (Taproot Cluster)" if is_exchange else ("Micro-Peel Transaction" if peel_val < 0.01 else "Intermediate Staging Wallet")

            risk_data = compute_risk_score({
                "address": peel_addr,
                "output_count": peel_count,
                "avg_value": sum(p["value"] for p in btc_data["all_peels"]) / max(peel_count, 1),
                "cross_chain_jump": False,
                "is_new_address": not redis_client.sismember("tracegraph:autonomous_run", peel_addr)
            })

            api_vasp_tag = build_vasp_lookup(peel_addr)
            
            # Subpoena Target Entity Resolution
            entity_info = resolve_entity(api_vasp_tag)
            platform_name = entity_info["name"] if entity_info else api_vasp_tag
            le_notes = entity_info["note"] if entity_info else ""

            cypher_query = """
            MERGE (s:CrossChainWallet {address: $sender})
            SET s.chain = 'Bitcoin'
            MERGE (d:CrossChainWallet {address: $recipient})
            SET d.chain = 'Bitcoin',
                d.classification = $entity_tag,
                d.risk_score = $risk_score,
                d.risk_level = $risk_level,
                d.risk_flags = $risk_flags,
                d.vasp_tag = $vasp_tag,
                d.platform = $platform,
                d.le_notes = $le_notes
            """
            if is_exchange:
                cypher_query += " SET d:ExchangeNode "
            
            cypher_query += """
            MERGE (s)-[t:TRANSFERRED_TO {hash: $tx_hash, value: $value, asset: 'BTC'}]->(d)
            SET t.chain = 'Bitcoin'
            """

            with db.driver.session() as session:
                session.run(
                    cypher_query,
                    sender=wallet_address, recipient=peel_addr, tx_hash=tx_hash, value=peel_val,
                    entity_tag=entity_tag, risk_score=risk_data["score"], risk_level=risk_data["level"],
                    risk_flags=", ".join(risk_data["flags"]), vasp_tag=api_vasp_tag or "Unknown",
                    platform=platform_name, le_notes=le_notes
                ).consume()

            if is_exchange:
                continue

            if peel_val >= 0.05:
                # Replaced .delay() with native asyncio create_task
                asyncio.create_task(trace_wallet_task(peel_addr, "bitcoin", current_depth + 1, max_depth))
        return

    # =====================================================
    # ETHEREUM TRACE LOGIC
    # =====================================================
    transfers = await fetch_outbound_transfers(wallet_address)
    if not transfers:
        return

    out_degree = len(transfers)
    unique_recipients = len(set(tx.get("to") for tx in transfers if tx.get("to")))
    total_value = sum(tx.get("value", 0) for tx in transfers if tx.get("value"))
    avg_value = total_value / out_degree if out_degree > 0 else 0
    velocity_ratio = unique_recipients / out_degree if out_degree > 0 else 0

    features = np.array([[out_degree, unique_recipients, avg_value, velocity_ratio]])
    if ml_pruner.predict(features)[0] == 1:
        print(f"🛑 [ML PRUNE] {wallet_address} resembles exchange.")
        db.driver.execute_query("MERGE (w:CrossChainWallet {address: $addr}) SET w:Exchange", addr=wallet_address)
        return

    valid_transfers = [tx for tx in transfers if tx.get("value") and tx.get("value") >= THRESHOLD]
    sorted_transfers = sorted(valid_transfers, key=lambda x: x.get("value", 0), reverse=True)

    for tx in sorted_transfers[:2]:
        recipient = tx.get("to")
        if not recipient: continue
        recipient = recipient.lower()

        value = tx.get("value")
        tx_hash = tx.get("hash", "unknown_hash")
        token_symbol = tx.get("asset") or tx.get("token") or tx.get("symbol") or "ETH"

        # Await directly instead of run_until_complete
        raw_input = await fetch_transaction_input(tx_hash)
        cross_chain_data = scan_for_cross_chain_payload(raw_input)
        
        api_vasp_tag = build_vasp_lookup(recipient)
        
        entity_info = resolve_entity(api_vasp_tag)
        platform_name = entity_info["name"] if entity_info else api_vasp_tag
        le_notes = entity_info["note"] if entity_info else ""

        is_thorchain = False
        if platform_name and "thorchain" in str(platform_name).lower():
            is_thorchain = True

        eth_risk = compute_risk_score({
            "address": recipient,
            "velocity_ratio": velocity_ratio,
            "avg_value": avg_value,
            "output_count": out_degree,
            "cross_chain_jump": bool(cross_chain_data) or is_thorchain,
            "is_new_address": not redis_client.sismember("tracegraph:autonomous_run", recipient),
            "entity_type": entity_info["type"] if entity_info else "UNKNOWN"
        })

        cypher_query = """
        MERGE (s:CrossChainWallet {address: $sender})
        SET s.chain = 'Ethereum'
        MERGE (d:CrossChainWallet {address: $recipient})
        SET d.chain = 'Ethereum',
            d.risk_score = $score,
            d.risk_level = $level,
            d.risk_flags = $flags,
            d.platform = $platform,
            d.le_notes = $le_notes,
            d.vasp_tag = $vasp_tag
        MERGE (s)-[t:TRANSFERRED_TO {hash: $tx_hash, value: $value, asset: $asset}]->(d)
        SET t.chain = 'Ethereum'
        """

        with db.driver.session() as session:
            session.run(
                cypher_query, sender=wallet_address, recipient=recipient, tx_hash=tx_hash, 
                value=value, asset=token_symbol, score=eth_risk["score"], level=eth_risk["level"],
                flags=", ".join(eth_risk["flags"]), platform=platform_name, 
                le_notes=le_notes, vasp_tag=api_vasp_tag or "Unknown"
            ).consume()

        print(f"💸 {wallet_address} -> {recipient} | {value} {token_symbol}")

        # =====================================================
        # BRIDGE RESOLUTION LOGIC
        # =====================================================
        if is_thorchain:
            print(f"🌉 [THORCHAIN] Dynamic router match via VASP tag — querying Midgard API...")
            thor_result = await resolve_thorchain_btc_output(tx_hash)

            if thor_result:
                dest_address = thor_result["btc_address"].lower()
                dest_chain = "bitcoin"
                btc_amount = thor_result["btc_amount"]

                print(f"🌉 [BRIDGE] ETH -> BTC: {dest_address[:20]}... ({btc_amount:.5f} BTC)")

                bridge_cypher = """
                MERGE (eth:CrossChainWallet {address: $evm_addr})
                MERGE (btc:CrossChainWallet {address: $btc_addr})
                SET btc.chain = 'Bitcoin',
                    btc.classification = 'BTC Receiver (THORChain)',
                    btc.risk_score = 90,
                    btc.risk_level = 'CRITICAL',
                    btc.risk_flags = 'THORChain bridge output — cross-chain evasion'
                MERGE (eth)-[t:BRIDGED_TO {hash: $tx_hash}]->(btc)
                SET t.value = $btc_amount, t.asset = 'BTC',
                    t.chain = 'Ethereum', t.target_chain = 'Bitcoin'
                """
                with db.driver.session() as session:
                    session.run(
                        bridge_cypher,
                        evm_addr=recipient, btc_addr=dest_address,
                        tx_hash=tx_hash, btc_amount=btc_amount
                    ).consume()

                asyncio.create_task(trace_wallet_task(dest_address, "bitcoin", current_depth + 1, max_depth))
                continue
            else:
                print("⚠️ THORChain API did not return a BTC output for this tx.")

        elif cross_chain_data:
            dest_chain = cross_chain_data["chain"]
            dest_address = cross_chain_data["address"].lower()
            print(f"🌉 [BRIDGE DETECTED] {dest_chain}: {dest_address}")

            bridge_cypher = """
            MERGE (eth:CrossChainWallet {address: $evm_router})
            MERGE (dest:CrossChainWallet {address: $dest_addr})
            SET dest.chain = $dest_chain
            MERGE (eth)-[t:BRIDGED_TO {hash: $tx_hash, asset: $asset}]->(dest)
            """
            with db.driver.session() as session:
                session.run(
                    bridge_cypher,
                    evm_router=recipient, dest_addr=dest_address,
                    dest_chain=dest_chain, tx_hash=tx_hash, asset=token_symbol
                ).consume()

            asyncio.create_task(trace_wallet_task(dest_address, dest_chain, current_depth + 1, max_depth))
            continue

        # If no bridge is detected, continue standard trace on the same chain
        asyncio.create_task(trace_wallet_task(recipient, "ethereum", current_depth + 1, max_depth))
