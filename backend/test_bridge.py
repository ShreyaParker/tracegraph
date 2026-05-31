import asyncio
from app.services.alchemy import fetch_transaction_input, scan_for_cross_chain_payload

async def test_extraction():
    # The exact TxHash from your Etherscan screenshot
    target_tx = "0xf4c84849ef78d4f2b475fb06aa1577c9f9b537fc591a6a421f2b09eaf4cd8e46"
    
    print(f"📡 Fetching raw hex payload from Alchemy for {target_tx}...")
    raw_hex = await fetch_transaction_input(target_tx)
    
    print("🧠 Cracking payload open with Regex engine...")
    result = scan_for_cross_chain_payload(raw_hex)
    
    if result:
        print(f"✅ SUCCESS! Extracted: {result}")
    else:
        print("❌ FAILED: No cross-chain address found.")

if __name__ == "__main__":
    asyncio.run(test_extraction())