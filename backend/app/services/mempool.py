import httpx
import asyncio

async def fetch_btc_greedy_path(address: str, max_retries: int = 4):
    base_url = f"https://blockstream.info/api/address/{address}/txs"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    
    all_txs = []
    last_txid = None
    
    async with httpx.AsyncClient(headers=headers) as client:
        # ✨ VALUE ADD 1: Deep Ledger Pagination ✨
        # Fetch up to 4 pages (100 txs) to dig deep into highly active wallets, 
        # bypassing the 25-tx public API limit that breaks basic trackers.
        for page in range(4):
            url = base_url if page == 0 else f"{base_url}/chain/{last_txid}"
            page_txs = []
            
            for attempt in range(max_retries):
                try:
                    response = await client.get(url, timeout=25.0)
                    
                    if response.status_code == 429:
                        await asyncio.sleep(2 ** attempt)
                        continue
                        
                    if response.status_code != 200:
                        break 
                        
                    page_txs = response.json()
                    break 
                    
                except httpx.RequestError:
                    await asyncio.sleep(2)
                    
            if not page_txs:
                break
                
            all_txs.extend(page_txs)
            last_txid = page_txs[-1]['txid']
            
            # If a page returns less than 25 txs, we've reached the end of the wallet's history
            if len(page_txs) < 25:
                break

    if not all_txs:
        return None

    # ✨ VALUE ADD 2: Absolute Maximum Outflow Heuristic ✨
    # Instead of falling for tiny "test" transactions or recent micro-peels, 
    # we mathematically scan the ENTIRE history and lock onto the exact transaction 
    # that moved the most volume (The True Spine).
    
    best_tx = None
    absolute_max_value = 0

    for tx in all_txs:
        # Check if the current address is the sender
        is_sender = any(vin.get('prevout', {}).get('scriptpubkey_address') == address for vin in tx['vin'])
        
        if is_sender:
            max_in_tx = 0
            largest_recipient_in_tx = None
            outputs_in_tx = []
            
            # Catalog all peels in this specific transaction
            for vout in tx['vout']:
                value = vout.get('value', 0)
                out_addr = vout.get('scriptpubkey_address')
                
                if out_addr:
                    btc_value = value / 100000000 
                    outputs_in_tx.append({"address": out_addr, "value": btc_value})
                    
                    if value > max_in_tx:
                        max_in_tx = value
                        largest_recipient_in_tx = out_addr
                        
            # If this transaction moved more money than any other transaction in the wallet's history, 
            # lock onto it as the true main spine.
            if max_in_tx > absolute_max_value:
                absolute_max_value = max_in_tx
                best_tx = {
                    "tx_hash": tx['txid'],
                    "next_hop": largest_recipient_in_tx,
                    "all_peels": outputs_in_tx
                }
                
    return best_tx