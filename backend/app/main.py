from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

# Import your actual crawling function directly instead of the task.delay
# (Replace 'trace_wallet_logic' with whatever function executes your scraping inside worker.py)
from app.worker import trace_wallet_logic 

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

    # This kicks off the function safely in a separate thread inside FastAPI
    background_tasks.add_task(trace_wallet_logic, address, chain, 0, request.max_depth)

    return {
        "status": "Trace initiated",
        "seed_address": address,
        "chain": chain,
        "message": "Internal worker thread is now crawling the blockchain."
    }

@app.get("/api/v1/health")
async def health_check():
    return {"status": "Tracegraph Engine Online"}
