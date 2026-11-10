"""Shared helpers for the T8a fixtures: OTel file exporter and a JSON-lines writer.

Imports only the stdlib and opentelemetry (present in both venvs). The OTel provider is configured only when
the harness sets T8A_OTEL_FILE; that is the operator action the pre-registration declares.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


def jsonl_append(path: str | Path, obj: dict[str, Any]) -> None:
    with open(path, "a", buffering=1) as f:
        f.write(json.dumps(obj, default=str, separators=(",", ":")) + "\n")


def server_env(base: dict[str, str]) -> dict[str, str]:
    """Env for a stdio server child: the SDK's safe default subset plus the server's own OTel file, if any."""
    env = dict(base)
    env["PYTHONUNBUFFERED"] = "1"
    if os.environ.get("T8A_SERVER_OTEL_FILE"):
        env["T8A_OTEL_FILE"] = os.environ["T8A_SERVER_OTEL_FILE"]
    if os.environ.get("T8A_HTTPX_INSTRUMENT"):
        env["T8A_HTTPX_INSTRUMENT"] = os.environ["T8A_HTTPX_INSTRUMENT"]
    return env


def configure_otel(service_name: str) -> str | None:
    """Install a TracerProvider with a JSON-lines file exporter if T8A_OTEL_FILE is set. Returns the path.

    A server process prefers T8A_SERVER_OTEL_FILE when present (stdio servers inherit the client's env)."""
    path = os.environ.get("T8A_OTEL_FILE")
    if "server" in service_name and os.environ.get("T8A_SERVER_OTEL_FILE"):
        path = os.environ["T8A_SERVER_OTEL_FILE"]
    if not path:
        return None
    Path(path).touch()  # an empty file means "exporter configured, zero spans"; no file means "not configured"
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

    class JsonlExporter(SpanExporter):
        def export(self, spans):  # type: ignore[override]
            for s in spans:
                ctx = s.get_span_context()
                parent = s.parent
                jsonl_append(path, {
                    "t_mono_ns": time.monotonic_ns(),
                    "name": s.name,
                    "kind": str(s.kind).split(".")[-1],
                    "trace_id": f"{ctx.trace_id:032x}",
                    "span_id": f"{ctx.span_id:016x}",
                    "parent_span_id": f"{parent.span_id:016x}" if parent else None,
                    "parent_remote": bool(parent.is_remote) if parent else None,
                    "status": str(s.status.status_code).split(".")[-1],
                    "status_desc": s.status.description,
                    "attributes": dict(s.attributes or {}),
                    "events": [{"name": e.name, "attributes": dict(e.attributes or {})} for e in s.events],
                    "start_ns": s.start_time, "end_ns": s.end_time,
                    "instrumentation_scope": s.instrumentation_scope.name if s.instrumentation_scope else None,
                    "service": service_name,
                })
            return SpanExportResult.SUCCESS

        def shutdown(self) -> None:
            return None

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(SimpleSpanProcessor(JsonlExporter()))
    trace.set_tracer_provider(provider)
    return path


# The fixed call script every cell runs (name, arguments). Resources and the second tools/list are driven by
# the client scripts by position; see client_v1.py / client_v2.py.
CALLS = [
    ("echo", {"text": "fixture hello"}),
    ("scan.v2-beta", {"target": "127.0.0.1"}),
    ("fail_tool", {"reason": "fixture failure"}),
    ("no_such_tool", {"x": 1}),
    ("echo", {}),  # required argument missing
    ("log_then_echo", {"text": "fixture log"}),
]
