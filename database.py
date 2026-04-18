import os
import aiomysql
import ssl
from dotenv import load_dotenv

load_dotenv()

# Check if we should use Cloud or Local
USE_CLOUD = os.getenv("TIDB_HOST") is not None

if USE_CLOUD:
    ca_path = os.getenv("TIDB_CA_PATH")
    if not os.path.exists(ca_path):
        print(f"CRITICAL ERROR: Database certificate file '{ca_path}' NOT FOUND!")
        print("Please ensure the .pem file is pushed to GitHub or uploaded to the server.")
    
    import ssl
    ctx = ssl.create_default_context(cafile=os.getenv("TIDB_CA_PATH"))
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_REQUIRED
    
    DB_CONFIG = {
        'host': os.getenv("TIDB_HOST"),
        'user': os.getenv("TIDB_USER"),
        'password': os.getenv("TIDB_PASSWORD"),
        'db': os.getenv("TIDB_DB"),
        'port': int(os.getenv("TIDB_PORT", 4000)),
        'autocommit': True,
        'ssl': ctx,
        'connect_timeout': 30
    }
    print("Database: Cloud (TiDB) Mode")
else:
    DB_CONFIG = {
        'host': 'localhost',
        'user': 'root',
        'password': 'Pushpesh@1104',
        'db': 'collegemanagementsoftware',
        'autocommit': True
    }
    print("Database: Localhost Mode")

class Database:
    _pool = None

    @classmethod
    async def get_pool(cls):
        if cls._pool is None or cls._pool._closed:
            try:
                cls._pool = await aiomysql.create_pool(**DB_CONFIG)
            except Exception as e:
                print(f"Failed to connect to DB: {e}")
                # Fallback or re-raise
                raise e
        return cls._pool

    @classmethod
    async def fetch_all(cls, query, args=None):
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, args or ())
                return await cur.fetchall()

    @classmethod
    async def fetch_one(cls, query, args=None):
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, args or ())
                return await cur.fetchone()

    @classmethod
    async def close(cls):
        if cls._pool:
            cls._pool.close()
            await cls._pool.wait_closed()
