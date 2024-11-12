from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

ADMIN_ID = 475953677
MASTER_IDS = {'6754920583'}

class EnvBaseSettings(BaseSettings):
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

class DBSettings(EnvBaseSettings):
    DATABASE_URL: str = "sqlite:///database.db"

class BotSettings(EnvBaseSettings):
    BOT_TOKEN: SecretStr
    RATE_LIMIT: int = 1
    CALLBACK_RATE_LIMIT: int = 1

class Settings(BotSettings, DBSettings):
    DEBUG: bool = False

settings = Settings()
