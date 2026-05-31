import os
import ssl
import redis
from dotenv import load_dotenv

load_dotenv()

redis_url = os.getenv("REDIS_URL", "")
clean_redis_url = redis_url.split("?")[0]

print("📡 Connecting to Upstash Redis safely via SCAN interface...")
try:
    redis_client = redis.Redis.from_url(
        clean_redis_url,
        ssl_cert_reqs=ssl.CERT_NONE
    )

    # Step 1: Clear the specific graph anti-loop memory
    print("🧹 Purging Aegis execution memory...")
    redis_client.delete("aegis:autonomous_run")

    # Step 2: Use SCAN to iteratively wipe the backed up celery queue backlog
    print("🌊 Scanning and flushing clogged task backlog...")
    cursor = 0
    deleted_count = 0
    
    while True:
        cursor, keys = redis_client.scan(cursor=cursor, count=100)
        if keys:
            redis_client.delete(*keys)
            deleted_count += len(keys)
        if cursor == 0:
            break

    print(f"✅ Success! Safely wiped {deleted_count} clogged records from Upstash Redis.")

except Exception as e:
    print(f"❌ Error clearing Redis: {e}")