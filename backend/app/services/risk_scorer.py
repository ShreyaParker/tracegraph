"""
Risk scoring engine for TraceGraph.
Produces a 0-100 score per wallet for investigator triage.
"""
ENTITY_DB = {
    # Centralised exchanges
    "binance":    {"type": "CEX",          "risk": 60, "note": "KYC available via law enforcement portal"},
    "okx":        {"type": "CEX",          "risk": 60, "note": "Law enforcement portal: law@okx.com"},
    "kraken":     {"type": "CEX",          "risk": 50, "note": "US subpoena process"},
    "coinbase":   {"type": "CEX",          "risk": 40, "note": "Highly cooperative — law@coinbase.com"},
    "paribu":     {"type": "CEX",          "risk": 55, "note": "Turkish exchange — local LE contact required"},
    # Swap services
    "changenow":  {"type": "SWAP_SERVICE", "risk": 70, "note": "Provides IP logs — compliance@changenow.io"},
    "fixedfloat": {"type": "SWAP_SERVICE", "risk": 70, "note": "Non-custodial, has IP log data"},
    "allbridge":  {"type": "BRIDGE",       "risk": 75, "note": "Provided user IP in Zoth investigation"},
    "thorchain":  {"type": "BRIDGE",       "risk": 80, "note": "Decentralised ETH→BTC bridge, no central operator"},
    # High-risk
    "tornado":    {"type": "MIXER",        "risk": 95, "note": "OFAC sanctioned. Notify FIU immediately."},
    "bitrefill":  {"type": "GIFT_CARD",    "risk": 80, "note": "Gift cards — provided IPs in Crystal investigations"},
    "roobet":     {"type": "GAMBLING",     "risk": 75, "note": "Offshore crypto casino, has user data"},
}
# Known VASP (Virtual Asset Service Provider) deposit address prefixes
KNOWN_VASPS = {
    "binance": [
        "bc1q7lccz9glmvee7gcg0hgkh0tddfmt4eyrw634hz",
        "1NDyJtNTjmwk5xPNhjgAMu4HDHigtobu1s",
    ],
    "okx": ["bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h"],
    "kraken": ["bc1q5shngj24323nsrmxv99st02nsvzk9rms9s9xpg"],
    "coinbase": ["bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"],
}

MIXER_PATTERNS = {
    "high_output_count": 5,   # >5 outputs = likely mixer/batch payout
    "taproot_cluster": "bc1p", # Taproot addresses used by mixers
    "long_address": 50,        # Overly long addresses = smart contracts / mixers
}

def compute_risk_score(wallet_data: dict) -> dict:
    score = 0.0
    flags = []
    vasp_tag = None

    # --- VASP / Exchange identification ---
    address = wallet_data.get("address", "").lower()
    for exchange_name, known_addresses in KNOWN_VASPS.items():
        if address in [a.lower() for a in known_addresses]:
            vasp_tag = exchange_name.upper()
            flags.append(f"Known {exchange_name.upper()} deposit address")
            score += 60  
            break

    # --- Mixer indicators ---
    output_count = wallet_data.get("output_count", 0)
    if output_count > MIXER_PATTERNS["high_output_count"]:
        score += 35
        flags.append(f"High output count ({output_count} outputs — possible mixer)")

    if address.startswith(MIXER_PATTERNS["taproot_cluster"]):
        score += 15
        flags.append("Taproot address (privacy tool)")

    # --- Behavioral indicators ---
    velocity_ratio = wallet_data.get("velocity_ratio", 0)
    if velocity_ratio > 0.85:
        score += 25
        flags.append(f"Sweeper behavior (velocity ratio: {velocity_ratio:.2f})")

    avg_value = wallet_data.get("avg_value", 0)
    if 0 < avg_value < 0.001:
        score += 15
        flags.append(f"Micro-peeling pattern (avg: {avg_value:.6f} BTC)")

    cross_chain = wallet_data.get("cross_chain_jump", False)
    if cross_chain:
        score += 30
        flags.append("Cross-chain bridge detected")

    score = min(score, 100.0)

    if score >= 75:
        level = "CRITICAL"
    elif score >= 50:
        level = "HIGH"
    elif score >= 25:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {
        "score": round(score, 1),
        "level": level,
        "flags": flags,
        "vasp_tag": vasp_tag,
    }

def build_vasp_lookup(address: str) -> str | None:
    address = address.lower()
    for name, addresses in KNOWN_VASPS.items():
        if address in [a.lower() for a in addresses]:
            return name.upper()
    return None