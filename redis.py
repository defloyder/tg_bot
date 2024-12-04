import aioredis

# Подключение к Redis
redis = aioredis.from_url("redis://localhost", decode_responses=True)
