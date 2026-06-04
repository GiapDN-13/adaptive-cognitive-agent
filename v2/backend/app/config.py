from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM Provider
    llm_provider: str = "bedrock"

    # AWS Bedrock
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    bedrock_light_model: str = "us.anthropic.claude-sonnet-4-6-v1"
    bedrock_heavy_model: str = "us.anthropic.claude-opus-4-6-v1"

    # Gemini fallback
    google_api_key: str = ""
    gemini_flash_model: str = "gemini-2.0-flash"
    gemini_pro_model: str = "gemini-2.5-pro"

    # Azure OpenAI (GPT-5.4)
    azure_openai_endpoint: str = "https://eastus2.api.cognitive.microsoft.com/openai/deployments/gpt-54/chat/completions?api-version=2024-02-01"
    azure_openai_api_key: str = "CywSY3nXq9IvpNqRdnl6ljjiaNJQMK2159Ai19VWANEZxgBpU0GGJQQJ99CEACHYHv6XJ3w3AAAAACOGJ1aY"

    # Cursor
    cursor_api_key: str = "crsr_ebfefd9f128472e33e5e838547ebe6ebd7a09f3d5760a7713e04bbb72e980fb3"
    cursor_proxy_url: str = "http://cursor-proxy:8001/v1/chat/completions"

    # Docker
    docker_base_url: str = "unix:///var/run/docker.sock"
    sandbox_image: str = "smartagent-sandbox:latest"
    container_default_mem: str = "512m"
    container_default_cpu: float = 1.0
    container_idle_timeout_min: int = 30

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
