"""Common tools and technologies, so the verifier notices them even when they appear in
lowercase and nobody listed them anywhere ("deployed with terraform").

Only unambiguous names: no "go", "r", "c", "rust", "swift"... (those are ordinary words or
need context). Add to this list when an eval case shows a term slipping through.
"""

TECH_TERMS = [
    # languages
    "python", "java", "javascript", "typescript", "golang", "kotlin", "scala", "ruby", "php", "perl",
    "c++", "c#", "objective-c", "haskell", "elixir", "clojure", "matlab", "bash", "powershell", "solidity",
    # web / backend
    "react", "react native", "next.js", "vue", "angular", "svelte", "node.js", "express.js", "django", "flask",
    "fastapi", "spring boot", "ruby on rails", "laravel", ".net", "asp.net", "graphql", "grpc", "websockets", "webrtc",
    "tailwind", "redux", "jquery", "nestjs",
    # data / storage
    "sql", "postgresql", "postgres", "mysql", "sqlite", "mongodb", "redis", "cassandra", "dynamodb",
    "elasticsearch", "snowflake", "bigquery", "redshift", "databricks", "spark", "pyspark", "hadoop", "kafka",
    "airflow", "dbt", "flink", "clickhouse", "neo4j", "supabase", "firebase",
    # cloud / devops
    "aws", "gcp", "azure", "aws lambda", "ec2", "s3", "kubernetes", "k8s", "docker", "terraform", "ansible",
    "jenkins", "github actions", "gitlab ci", "circleci", "helm", "prometheus", "grafana", "datadog", "nginx",
    "linux", "vercel", "heroku", "cloudflare",
    # ml / ai
    "pytorch", "tensorflow", "keras", "scikit-learn", "pandas", "numpy", "hugging face", "transformers",
    "langchain", "langgraph", "llamaindex", "openai", "pinecone", "weaviate", "chromadb", "faiss", "mlflow",
    "rag", "llm", "llms", "nlp", "computer vision", "opencv", "xgboost",
    # tools / platforms
    "jira", "figma", "salesforce", "servicenow", "sap", "tableau", "power bi", "microsoft excel", "selenium", "playwright",
    "cypress", "jest", "pytest", "junit", "unity3d", "unreal", "ios", "android", "swiftui", "flutter",
]
