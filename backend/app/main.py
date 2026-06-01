from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from app.worker import trace_wallet_task 

app = FastAPI(title="Project Aegis - TraceGraph Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TraceRequest(BaseModel):
    seed_address: str
    chain: Optional[str] = "ethereum"
    max_depth: int = 8

@app.post("/api/v1/trace")
async def start_trace(request: TraceRequest, background_tasks: BackgroundTasks):
    address = request.seed_address.lower()
    chain = request.chain.lower()

    if chain == "ethereum":
        if not address.startswith("0x") or len(address) != 42:
            raise HTTPException(status_code=400, detail="Invalid EVM address format.")
    elif chain == "bitcoin":
        if not (address.startswith("bc1") or address.startswith("1") or address.startswith("3")):
            raise HTTPException(status_code=400, detail="Invalid Bitcoin address format.")
    else:
        raise HTTPException(status_code=400, detail="Unsupported chain.")

    # Pass background_tasks as the final argument so the worker can queue up sub-hops
    background_tasks.add_task(trace_wallet_task, address, chain, 0, request.max_depth, background_tasks)

    return {
        "status": "Trace initiated",
        "seed_address": address,
        "chain": chain,
        "message": "Aegis background multi-threading engine tracking hops safely."
    }

@app.get("/api/v1/health")
async def health_check():
    return {"status": "Aegis Engine Online"}
