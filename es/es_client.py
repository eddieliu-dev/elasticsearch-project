"""Connect to a local or authenticated Elasticsearch 8.x cluster."""

from functools import lru_cache
from pathlib import Path

from elasticsearch import Elasticsearch

from config import ELASTICSEARCH_API_KEY, ELASTICSEARCH_CA_CERTS, ELASTICSEARCH_URL, ROOT


@lru_cache(maxsize=1)
def get_client() -> Elasticsearch:
    options = {"request_timeout": 60}
    if ELASTICSEARCH_API_KEY:
        options["api_key"] = ELASTICSEARCH_API_KEY
    if ELASTICSEARCH_CA_CERTS:
        certificate = Path(ELASTICSEARCH_CA_CERTS).expanduser()
        options["ca_certs"] = str(certificate if certificate.is_absolute() else ROOT / certificate)
    return Elasticsearch(ELASTICSEARCH_URL, **options)
