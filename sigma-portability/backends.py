"""The four open backends under test, each with its idiomatic field-mapping pipeline.

The pipeline matters: it renames the rule's Windows field names into the target's
schema (ECS for Elasticsearch/OpenSearch, the Splunk model for SPL), which is part
of what "translation" does. The correlation structure — aggregation, group-by,
threshold, time window — is what this benchmark scores, but the field renaming is
recorded too because a field that lands under a different name is a real
portability fact.

All four emit text; no commercial software runs, so the benchmark is fully public.
"""

from sigma.backends.splunk import SplunkBackend
from sigma.backends.elasticsearch import ESQLBackend, LuceneBackend
from sigma.backends.opensearch import OpenSearchPPLBackend
from sigma.pipelines.splunk import splunk_windows_pipeline
from sigma.pipelines.elasticsearch.windows import ecs_windows


def build_backends():
    """Return an ordered dict: target-name -> (backend, pipeline-name)."""
    return {
        "splunk_spl": (SplunkBackend(processing_pipeline=splunk_windows_pipeline()), "splunk_windows"),
        "es_esql": (ESQLBackend(processing_pipeline=ecs_windows()), "ecs_windows"),
        "es_lucene": (LuceneBackend(processing_pipeline=ecs_windows()), "ecs_windows"),
        "os_ppl": (OpenSearchPPLBackend(processing_pipeline=ecs_windows()), "ecs_windows"),
    }


# Human labels for the writeup.
BACKEND_LABELS = {
    "splunk_spl": "Splunk SPL",
    "es_esql": "Elasticsearch ES|QL",
    "es_lucene": "Elasticsearch Lucene",
    "os_ppl": "OpenSearch PPL",
}
