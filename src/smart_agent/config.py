from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM Provider: "gemini" or "bedrock"
    llm_provider: str = "bedrock"

    # Gemini settings
    google_api_key: str = ""
    gemini_flash_model: str = "gemini-2.0-flash"
    gemini_pro_model: str = "gemini-2.5-pro"

    # AWS Bedrock settings
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    bedrock_light_model: str = "us.anthropic.claude-sonnet-4-6-v1"
    bedrock_heavy_model: str = "us.anthropic.claude-opus-4-6-v1"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
