# Elasticsearch Document Search with Local LLM Enrichment

Search documents across **titles, keywords, and content** using Elasticsearch. A local **Ollama** model creates structured metadata during ingestion; Elasticsearch handles indexing and ranked full-text retrieval.

This project demonstrates a complete small ingestion-and-search workflow: input parsing, validated LLM enrichment, explicit index mappings, repeatable writes, and multi-field queries. Search returns source documents rather than generated answers.

**Companion project:** [Local Semantic Document Search](https://github.com/eddieliu-dev/chroma-vdb-project) uses Chroma and BGE-M3 embeddings over the same sample documents. The two repositories demonstrate different retrieval approaches and can be run independently.

## At a glance

- **Ingestion:** UTF-8 text → validated title and keywords from Ollama → Elasticsearch documents.
- **Retrieval:** full-text search across `title`, `keywords`, and `content`, with field boosts.
- **Preserved data:** ingestion creates the index only when absent and never deletes existing records.
- **Repeatable imports:** content-based IDs update identical documents instead of duplicating them.
- **Local demo:** Docker Compose provides Elasticsearch 8.x; six synthetic sample documents are included.

## How it works

```mermaid
flowchart LR
    A[One document per line] --> B[Ollama: title and keywords]
    A --> C[Document with content-based ID]
    B --> C
    C --> D[(Elasticsearch index)]
    Q[Search query] --> E[Multi-field full-text query]
    E --> D
    D --> R[Ranked documents and scores]
```

Metadata is generated once per document using an Ollama JSON schema, then validated before indexing. The query path uses Elasticsearch directly and does not require Ollama to be running.

## Quick start

### 1. Install dependencies

Use Python **3.11 or 3.12**, Docker with Compose, and [Ollama](https://docs.ollama.com/quickstart).

```bash
git clone https://github.com/eddieliu-dev/elasticsearch-practice.git
cd elasticsearch-practice
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

### 2. Start Elasticsearch

```bash
docker compose up -d --wait
```

The included service binds to `127.0.0.1:9200`, disables authentication for local development, and persists documents in a named Docker volume. It uses Elasticsearch **8.19.23** and a compatible 8.x Python client. For an existing authenticated cluster, configure its URL, API key, and CA certificate in `.env` instead of starting this service.

### 3. Start Ollama and download the model

If Ollama is not already running, run this in a separate terminal:

```bash
ollama serve
```

Then download the generation model:

```bash
ollama pull llama3.1:latest
```

### 4. Ingest and search

```bash
python main.py ingest
python main.py count
python main.py query "solar electricity" --limit 3
```

With a fresh default index, `count` returns:

```json
{
  "index": "documents",
  "count": 6
}
```

Search returns a JSON array containing `id`, `score`, `title`, `keywords`, `content`, `source`, and `ingested_at`. **Higher Elasticsearch scores rank first.** For this query, inspect the rooftop-solar and battery documents; generated metadata can affect ordering. Scores are specific to the query and index and are not comparable to Chroma distances.

Progress messages go to stderr and JSON results go to stdout:

```bash
python main.py query "public transport" --limit 2 > results.json
```

To stop the local Elasticsearch service while retaining indexed data:

```bash
docker compose down
```

## CLI and input format

```bash
python main.py --help
python main.py ingest --file data/sample.txt --index demo
python main.py query "coastal flooding" --index demo --limit 2
python main.py count --index demo
```

Each nonempty line is one complete document. Files are read as UTF-8, surrounding whitespace is stripped, and blank lines are skipped. `data/sample.txt` is the default synthetic dataset; the original Chinese news fixtures remain available through `--file`.

Ingestion creates a missing index and leaves an existing index intact. Identical text maps to the same SHA-256 ID, so reruns replace that document, regenerate its metadata, and update its ingestion time. Edited text gets a new ID; old versions are not automatically removed. Imports are not transactional: an interruption can leave partial results, and a rerun safely reuses the same IDs. The index is refreshed after a successful import so newly ingested documents are immediately searchable.

## Configuration

Settings are loaded from the repository's `.env` file; exported environment variables take precedence.

| Variable | Default | Purpose |
| --- | --- | --- |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server for ingestion |
| `OLLAMA_MODEL` | `llama3.1:latest` | Title and keyword generation |
| `OLLAMA_TIMEOUT` | `300` | Timeout in seconds for each model request |
| `ELASTICSEARCH_URL` | `http://localhost:9200` | Elasticsearch 8.x endpoint |
| `ELASTICSEARCH_INDEX` | `documents` | Default index name |
| `ELASTICSEARCH_API_KEY` | Empty | Optional API key for an authenticated cluster |
| `ELASTICSEARCH_CA_CERTS` | Empty | Optional CA certificate path for HTTPS |

Keep credentials in `.env` or exported environment variables. `.env`, virtual environments, and IDE/cache files are ignored by Git; the example configuration contains no credentials. TLS certificate verification remains enabled for HTTPS connections.

## Search design and tradeoffs

The index maps `title`, `keywords`, and `content` as `text`, `source` as `keyword`, and `ingested_at` as `date`. Keywords are stored as a JSON array of strings. A `multi_match` query searches these fields:

| Field | Boost | Purpose |
| --- | --- | --- |
| `title` | 3 | Prefer terms in the generated document summary |
| `keywords` | 2 | Include relevant concepts extracted during ingestion |
| `content` | 1 | Match the original source text |

These boosts are illustrative choices, not tuned evaluation results. Elasticsearch provides lexical ranking using its default BM25 similarity. Unlike the Chroma companion, this implementation does not embed queries or documents. Lexical search is useful for explicit terminology; semantic retrieval can find related wording with less term overlap.

The source path and actual UTC ingestion time replace synthetic author names and dates. Content IDs make reruns safe from duplicate records, but identical text from different files shares one record.

## Tests

```bash
python -m unittest discover -s tests -v
```

Tests cover index preservation, explicit mappings, stable ingestion IDs, index refresh, multiple search hits, empty results, integer counts, optional authentication, and metadata validation. Elasticsearch and Ollama calls are mocked; no Docker daemon, running services, or downloaded model is needed. GitHub Actions runs the suite on Python 3.11 and 3.12.

## Project layout

```text
main.py                 CLI and ingestion workflow
config.py               Environment and .env configuration
compose.yaml            Local Elasticsearch service and persistent volume
es/                     Client, index mapping, and search operations
llm/                    Validated Ollama metadata extraction
helpers/                Input reading, content IDs, metadata, and prompts
data/sample.txt         Six synthetic demo documents
tests/                  Model-free regression tests
.github/workflows/      Automated checks
```

## Limitations and next steps

This is a small search prototype with sequential ingestion and default text analysis. It does not yet use bulk indexing, language-specific analyzers, retrieval benchmarks, hybrid vector search, or answer generation. The default analyzer is not tuned for Chinese word segmentation. A useful next step is a shared evaluation set with the Chroma companion, followed by analyzer tuning and hybrid retrieval.

## Troubleshooting

- **Cannot connect to Elasticsearch:** check `docker compose ps`, `docker compose logs elasticsearch`, and `ELASTICSEARCH_URL`.
- **Port 9200 is occupied:** use the existing service or change the Compose host port and `ELASTICSEARCH_URL` together.
- **Authentication or certificate error:** check the API key, endpoint scheme, and CA certificate for your cluster.
- **Ollama request fails:** check `ollama list`, `OLLAMA_MODEL`, and whether `ollama serve` is running. Increase `OLLAMA_TIMEOUT` for slow hardware.
- **Index does not exist:** run `ingest` with the same `--index` before querying or counting.

Implementation references: [Elasticsearch Docker setup](https://www.elastic.co/guide/en/elasticsearch/reference/8.19/docker.html), [Python client connections](https://www.elastic.co/guide/en/elasticsearch/client/python-api/8.19/connecting.html), and [Ollama generation API](https://docs.ollama.com/api/generate).
