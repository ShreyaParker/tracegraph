import os
import httpx
import re
import binascii
from dotenv import load_dotenv

load_dotenv()

ALCHEMY_KEY = os.getenv("ALCHEMY_API_KEY")
BASE_URL = os.getenv("ALCHEMY_URL", "https://eth-mainnet.g.alchemy.com/v2/").rstrip("/") + "/"

async def fetch_outbound_transfers(wallet_address: str):
    """Fetches all outbound ETH and ERC-20 transfers for a given wallet."""
    url = f"{BASE_URL}{ALCHEMY_KEY}"
    
    payload = {
        "id": 1,
        "jsonrpc": "2.0",
        "method": "alchemy_getAssetTransfers",
        "params": [{
            "fromBlock": "0x0",
            "toBlock": "latest",
            "fromAddress": wallet_address,
            "category": ["external", "erc20"],
            "excludeZeroValue": True
        }]
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("result", {}).get("transfers", [])
        except Exception as e:
            print(f"Alchemy Request Failed: {e}")
            return []

async def fetch_transaction_input(tx_hash: str):
    """Fetches the raw hexadecimal input data of a specific transaction."""
    url = f"{BASE_URL}{ALCHEMY_KEY}"
    payload = {
        "id": 1,
        "jsonrpc": "2.0",
        "method": "eth_getTransactionByHash",
        "params": [tx_hash]
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload)
            data = response.json()
            # Return the input hex data (e.g., '0xf4c84849...')
            return data.get("result", {}).get("input", "")
        except Exception as e:
            print(f"Failed to fetch tx payload for {tx_hash}: {e}")
            return ""

def scan_for_cross_chain_payload(hex_input: str):
    """
    Safely decodes raw hex input and uses Regex to extract cross-chain bridge routing.
    """
    if not hex_input or hex_input == "0x" or len(hex_input) < 10:
        return None
        
    try:
        # 1. Clean the hex string and fix odd-length padding (which crashes Python's unhexlify)
        clean_hex = hex_input[2:]
        if len(clean_hex) % 2 != 0:
            clean_hex = "0" + clean_hex
            
        # 2. Decode to raw bytes, then to UTF-8 (ignoring smart contract garbage characters)
        raw_bytes = binascii.unhexlify(clean_hex)
        decoded_text = raw_bytes.decode('utf-8', errors='ignore')
        
        # ==========================================
        # 3. THORCHAIN EXPLICIT MEMO ROUTING
        # ==========================================
        # Matches formats like: SWAP:BTC.BTC:bc1q... or SWAP:ETH.USDC:0x...
        memo_match = re.search(r'SWAP:[^:]+:([^:]+)', decoded_text, re.IGNORECASE)
        
        if memo_match:
            dest_address = memo_match.group(1).split(':')[0] # Clean any trailing colons
            
            # Auto-detect the destination chain based on address format
            chain = "Unknown Bridge"
            if dest_address.startswith(("bc1", "1", "3")):
                chain = "Bitcoin"
            elif dest_address.startswith("T") and len(dest_address) == 34:
                chain = "Tron"
            elif len(dest_address) >= 43 and not dest_address.startswith("0x"):
                chain = "Solana"
                
            return {
                "chain": chain, 
                "address": dest_address,
                "type": "THORChain Swap Memo"
            }
            
        # ==========================================
        # 4. FALLBACK: RAW REGEX HUNTING
        # ==========================================
        btc_match = re.search(r'(bc1[a-zA-Z0-9]{25,39}|[13][a-zA-Z0-9]{25,34})', decoded_text)
        if btc_match:
            return {
                "chain": "Bitcoin", 
                "address": btc_match.group(1),
                "type": "Raw Regex Extraction"
            }
            
    except Exception as e:
        print(f"⚠️ Payload Decode Error: {e}")
        pass
    
    return None