# ProRAG Settings Reference

All settings use Pydantic v2 BaseSettings with `PROVRAG_` prefix and `__` nested delimiter.

Source: `.env` file or system environment variables.

## Settings Class

```python
from provrag.settings import Settings, get_settings, Environment, LLMProvider

settings = get_settings()  # Cached singleton

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PROVRAG_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Environment = Environment.LOCAL   # "local" or "aws"
    debug: bool = False
    log_level: str = "INFO"                        # DEBUG|INFO|WARNING|ERROR|CRITICAL
    llm_provider: LLMProvider | None = None        # "bedrock" or "openai", auto-derived

    opensearch: OpenSearchSettings
    prefect: PrefectSettings
    phoenix: PhoenixSettings
    s3: S3Settings
    bedrock: BedrockSettings

    @computed_field
    @property
    def is_local(self) -> bool:
        return self.environment == Environment.LOCAL
```

LLM provider auto-derivation: if `llm_provider` is not set, it defaults to `BEDROCK` when `environment=aws`, `OPENAI` when `environment=local`.

## Environment Variables

### Core

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `PROVRAG_ENVIRONMENT` | `local` \| `aws` | `local` | Runtime environment |
| `PROVRAG_DEBUG` | bool | `false` | Debug mode |
| `PROVRAG_LOG_LEVEL` | str | `INFO` | Log level |
| `PROVRAG_LLM_PROVIDER` | `bedrock` \| `openai` | (derived) | LLM provider override |

### OpenSearch (`PROVRAG_OPENSEARCH__*`)

| Variable | Default | Description |
|----------|---------|-------------|
| `PROVRAG_OPENSEARCH__HOST` | `localhost` | OpenSearch host |
| `PROVRAG_OPENSEARCH__PORT` | `9200` | OpenSearch port |
| `PROVRAG_OPENSEARCH__USE_SSL` | `false` | Enable SSL |
| `PROVRAG_OPENSEARCH__VERIFY_CERTS` | `false` | Verify SSL certificates |
| `PROVRAG_OPENSEARCH__AWS_REGION` | `us-east-1` | AWS region for SigV4 signing |
| `PROVRAG_OPENSEARCH__SIGNING_HOST` | (none) | Real VPC endpoint hostname for SSM tunnel SigV4 |

### S3 / MinIO (`PROVRAG_S3__*`)

| Variable | Default | Description |
|----------|---------|-------------|
| `PROVRAG_S3__ENDPOINT_URL` | `http://localhost:9005` | S3/MinIO endpoint (null for real S3) |
| `PROVRAG_S3__BUCKET` | `provrag-documents` | Document bucket name |
| `PROVRAG_S3__AWS_REGION` | `us-east-1` | AWS region |
| `PROVRAG_S3__ACCESS_KEY` | `minioadmin` | MinIO access key (null for real S3) |
| `PROVRAG_S3__SECRET_KEY` | `minioadmin` | MinIO secret key (null for real S3) |

### Prefect (`PROVRAG_PREFECT__*`)

| Variable | Default | Description |
|----------|---------|-------------|
| `PROVRAG_PREFECT__API_URL` | `http://localhost:4200/api` | Prefect server API URL |

Note: Also set `PREFECT_API_URL` (no `PROVRAG_` prefix) as an env var for the Prefect client.

### Phoenix (`PROVRAG_PHOENIX__*`)

| Variable | Default | Description |
|----------|---------|-------------|
| `PROVRAG_PHOENIX__ENDPOINT` | `http://localhost:6006/v1/traces` | Phoenix OTEL collector endpoint |
| `PROVRAG_PHOENIX__PROJECT_NAME` | `provrag` | Phoenix project name |

### Bedrock (`PROVRAG_BEDROCK__*`)

| Variable | Default | Description |
|----------|---------|-------------|
| `PROVRAG_BEDROCK__AWS_REGION` | `us-east-1` | Bedrock region |
| `PROVRAG_BEDROCK__EMBEDDING_MODEL_ID` | `amazon.titan-embed-text-v2:0` | Embedding model |
| `PROVRAG_BEDROCK__LLM_MODEL_ID` | `anthropic.claude-3-sonnet-20240229-v1:0` | LLM model |

## Local Environment Example (.env)

```bash
PROVRAG_ENVIRONMENT=local
PROVRAG_DEBUG=true
PROVRAG_LOG_LEVEL=DEBUG

PROVRAG_OPENSEARCH__HOST=localhost
PROVRAG_OPENSEARCH__PORT=9200

PROVRAG_S3__ENDPOINT_URL=http://localhost:9005
PROVRAG_S3__BUCKET=provrag-documents
PROVRAG_S3__ACCESS_KEY=minioadmin
PROVRAG_S3__SECRET_KEY=minioadmin

PREFECT_API_URL=http://localhost:4200/api
PROVRAG_PREFECT__API_URL=http://localhost:4200/api

PROVRAG_PHOENIX__ENDPOINT=http://localhost:6006/v1/traces
PROVRAG_PHOENIX__PROJECT_NAME=my-project
```

## AWS Environment Example (.env)

```bash
PROVRAG_ENVIRONMENT=aws
PROVRAG_LOG_LEVEL=INFO
AWS_PROFILE=provectus-demos

PROVRAG_OPENSEARCH__HOST=localhost
PROVRAG_OPENSEARCH__PORT=9200
PROVRAG_OPENSEARCH__USE_SSL=true
PROVRAG_OPENSEARCH__VERIFY_CERTS=false
PROVRAG_OPENSEARCH__AWS_REGION=us-east-2
PROVRAG_OPENSEARCH__SIGNING_HOST=<vpc-opensearch-endpoint>

PROVRAG_S3__BUCKET=<s3-bucket-name>
# No endpoint_url, access_key, secret_key -- uses IAM

PREFECT_API_URL=http://localhost:4200/api
PROVRAG_PREFECT__API_URL=http://localhost:4200/api

PROVRAG_PHOENIX__ENDPOINT=http://localhost:6006/v1/traces
PROVRAG_PHOENIX__PROJECT_NAME=my-project

OPENSEARCH_ENDPOINT=<vpc-opensearch-endpoint>
```

Note: In AWS mode with SSM tunnels (`task connect`), services are accessed via localhost ports but signed with the real VPC endpoint hostname via `signing_host`.
