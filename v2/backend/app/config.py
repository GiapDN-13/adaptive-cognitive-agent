from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM Provider
    llm_provider: str = "bedrock"

    # AWS Bedrock
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    # Required when using temporary/STS credentials (access keys starting with ASIA).
    aws_session_token: str = ""
    aws_region: str = "us-east-1"
    bedrock_light_model: str = "us.anthropic.claude-sonnet-4-6-v1"
    bedrock_heavy_model: str = "us.anthropic.claude-opus-4-6-v1"
    # Per-request output cap. Lowered from 64000 to reduce capacity reservation
    # (a contributor to throttle / "no data for 120s" stalls). Kept at 16K — not
    # lower — because the agent writes large source files via write_file, whose
    # content is model OUTPUT; cutting a toolUse mid-JSON would corrupt the call.
    # The continuation loop handles legitimate longer text turns transparently.
    bedrock_max_tokens: int = 16384
    # Model routing: route heavy one-shot reasoning to Opus. Off by default
    # because Opus is much slower and caused timeouts when used per-turn.
    enable_model_routing: bool = False

    # Firecrawl self-hosted (anti-detection web: JS render + proxy + crawl/map).
    # Empty url → web_search falls back to free DuckDuckGo engines. Set to the
    # self-hosted endpoint to enable JS-wall scraping + site_map/crawl_site tools.
    firecrawl_url: str = "http://host.docker.internal:3002"
    firecrawl_api_key: str = "fc-smartagent-local"

    # Gemini fallback
    google_api_key: str = ""
    gemini_flash_model: str = "gemini-2.0-flash"
    gemini_pro_model: str = "gemini-2.5-pro"

    # Azure OpenAI (GPT-5.4) — key loaded from env (AZURE_OPENAI_API_KEY), never hardcoded.
    azure_openai_endpoint: str = "https://eastus2.api.cognitive.microsoft.com/openai/deployments/gpt-54/chat/completions?api-version=2024-02-01"
    azure_openai_api_key: str = ""

    # Cursor — key loaded from env (CURSOR_API_KEY), never hardcoded.
    cursor_api_key: str = ""
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
