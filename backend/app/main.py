from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.worker import trace_wallet_task

app = FastAPI(title="Project Aegis - TraceGraph Engine")

class TraceRequest(BaseModel):
    seed_address: str
    chain: Optional[str] = "ethereum"  # Defaults to ethereum, but accepts bitcoin
    max_depth: int = 8

@app.post("/api/v1/trace")
async def start_trace(request: TraceRequest):
    address = request.seed_address.lower()
    chain = request.chain.lower()

    # Validation logic based on the requested chain
    if chain == "ethereum":
        if not address.startswith("0x") or len(address) != 42:
            raise HTTPException(status_code=400, detail="Invalid EVM wallet address format.")
    elif chain == "bitcoin":
        if not (address.startswith("bc1") or address.startswith("1") or address.startswith("3")):
            raise HTTPException(status_code=400, detail="Invalid Bitcoin wallet address format.")
    else:
        raise HTTPException(status_code=400, detail="Unsupported chain. Use 'ethereum' or 'bitcoin'.")
    
    # Kick off the asynchronous Celery task with the new chain parameter
    trace_wallet_task.delay(address, chain, 0, request.max_depth)
    
    return {
        "status": "Trace initiated",
        "seed_address": address,
        "chain": chain,
        "message": f"Workers are now crawling the {chain.upper()} blockchain asynchronously."
    }

@app.get("/api/v1/health")
async def health_check():
    return {"status": "Aegis Engine Online"}