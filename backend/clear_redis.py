import redis
import ssl
from dotenv import load_dotenv
import os

load_dotenv()

redis_url = os.getenv("REDIS_URL", "")
# Strip query parameters so the client initializes smoothly
clean_redis_url = redis_url.split("?")[0]

try:
    print("📡 Connecting to Upstash Redis...")
    r = redis.Redis.from_url(
        clean_redis_url,
        ssl_cert_reqs=ssl.CERT_NONE
    )
    
    # Check current queue size
    print(f"📊 Current keys in database before flush: {len(r.keys('*'))}")
    
    # Flush all keys
    print("🧹 Flushing all tasks from the queue...")
    r.flushall()
    
    print("✨ Redis database completely cleared and ready for a fresh trace!")
    
except Exception as e:
    print(f"❌ Failed to clear Redis: {e}")