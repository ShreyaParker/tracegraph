"""
THORChain bridge resolver.
Given an Ethereum tx hash that sent funds to the THORChain Router,
returns the outbound BTC address and amount using the free Midgard API.
No API key required.
"""
import httpx
import asyncio

MIDGARD_BASE = "https://midgard.ninerealms.com/v2"

async def resolve_thorchain_btc_output(eth_tx_hash: str) -> dict | None:
    """
    Query THORChain Midgard API to find the BTC output address
    for a given inbound ETH transaction hash.

    Returns: {"btc_address": "bc1q...", "btc_amount": 23.255, "status": "success"}
    or None if not found.
    """
    url = f"{MIDGARD_BASE}/actions"
    params = {"txid": eth_tx_hash.lower().lstrip("0x")}

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                print(f"⚠️ Midgard API returned {response.status_code}")
                return None

            data = response.json()
            actions = data.get("actions", [])

            if not actions:
                print(f"⚠️ No THORChain actions found for tx {eth_tx_hash[:20]}...")
                return None

            for action in actions:
                # Look for the outbound transaction on Bitcoin chain
                for out_tx in action.get("out", []):
                    coins = out_tx.get("coins", [])
                    address = out_tx.get("address", "")

                    # Bitcoin addresses start with bc1 or 1 or 3
                    if address.startswith(("bc1", "1", "3")):
                        btc_amount = 0
                        for coin in coins:
                            if coin.get("asset", "").upper() == "BTC.BTC":
                                # THORChain uses 8-decimal integer amounts
                                raw = coin.get("amount", "0")
                                btc_amount = int(raw) / 1e8
                                break

                        print(f"🌉 [THORCHAIN] ETH tx {eth_tx_hash[:20]}... → BTC {address[:20]}... ({btc_amount:.5f} BTC)")
                        return {
                            "btc_address": address,
                            "btc_amount": btc_amount,
                            "status": action.get("status", "unknown"),
                            "type": action.get("type", "swap"),
                        }

            print(f"⚠️ No BTC outbound found in THORChain actions for {eth_tx_hash[:20]}")
            return None

        except Exception as e:
            print(f"⚠️ THORChain resolver error: {e}")
            return None