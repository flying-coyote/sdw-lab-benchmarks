"""Validate flattened OCSF 1.9.0 field paths (a_b_c == a.b.c) against the local schema dump that R1 fetched
from schema.ocsf.io/api/1.9.0 (profiles applied). List attributes are flattened at element 0 (one element
per event in these fixtures). Run: .venv/bin/python -I ocsf_fields.py  -> prints OK/FAIL per column."""
import json, os, sys
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "atlas-ocsf-observables", "sources", "ocsf-1.9.0")
_cache = {}
def load(kind, name):
    k = (kind, name)
    if k not in _cache:
        _cache[k] = json.load(open(os.path.join(SRC, kind, name + ".json")))
    return _cache[k]
def resolve(cls, path):
    """Return the dotted OCSF path for a flattened column, or None. Greedy on attribute names containing '_'."""
    attrs = load("classes", cls)["attributes"]
    parts = path.split("_"); out = []
    i = 0
    while i < len(parts):
        hit = None
        for j in range(len(parts), i, -1):  # longest attribute name first
            cand = "_".join(parts[i:j])
            if cand in attrs:
                hit = (cand, j); break
        if not hit:
            return None
        name, i = hit; out.append(name)
        a = attrs[name]
        if i < len(parts):
            ot = a.get("object_type")
            if not ot:
                return None
            attrs = load("objects", ot)["attributes"]
    return ".".join(out)
TABLES = {  # OCSF class -> columns the fixtures use (metadata/time columns included)
 "authentication": ["time", "class_uid", "activity_id", "user_name", "user_type_id", "src_endpoint_ip", "src_endpoint_autonomous_system_number", "status_id", "is_mfa", "service_name", "dst_endpoint_hostname", "authentication_token_type_id", "metadata_product_name"],
 "api_activity": ["time", "class_uid", "activity_id", "api_operation", "api_service_name", "api_request_uid", "api_request_data", "api_response_data", "actor_user_name", "actor_user_type_id", "actor_app_name", "src_endpoint_ip", "src_endpoint_autonomous_system_number", "ai_model_name", "ai_agent_name", "ai_agent_uid", "delegation_uid", "delegation_issuer_uid", "message_context_prompt_text", "message_context_response_text", "message_context_total_tokens", "metadata_product_name", "status_id", "http_request_url"],
 "account_change": ["time", "class_uid", "activity_id", "user_name", "actor_user_name", "actor_process_name", "actor_process_cmd_line", "ai_agent_name", "delegation_uid", "src_endpoint_ip", "device_hostname", "status_id", "metadata_product_name"],
 "process_activity": ["time", "class_uid", "activity_id", "process_name", "process_cmd_line", "process_path", "process_file_signature_state_id", "process_container_name", "actor_process_name", "actor_process_path", "actor_user_name", "device_hostname", "metadata_product_name"],
 "module_activity": ["time", "class_uid", "activity_id", "module_file_path", "module_file_name", "module_file_signature_state_id", "module_load_type_id", "module_function_name", "actor_process_name", "actor_process_cmd_line", "actor_process_path", "actor_user_name", "device_hostname", "metadata_product_name"],
 "file_activity": ["time", "class_uid", "activity_id", "file_path", "file_name", "file_ext", "file_size", "file_signature_state_id", "file_uri", "actor_user_name", "actor_process_name", "actor_process_cmd_line", "device_hostname", "metadata_product_name"],
 "datastore_activity": ["time", "class_uid", "activity_id", "type_id", "database_name", "databucket_name", "table_name", "query_info_query_string", "query_info_bytes", "actor_user_name", "actor_user_type_id", "src_endpoint_ip", "status_id", "metadata_product_name"],
 "network_activity": ["time", "class_uid", "activity_id", "src_endpoint_ip", "dst_endpoint_ip", "dst_endpoint_domain", "dst_endpoint_port", "traffic_bytes_out", "url_hostname", "metadata_product_name"],
 "email_activity": ["time", "class_uid", "activity_id", "direction_id", "email_from", "email_to", "email_bcc", "email_subject", "email_message_uid", "actor_app_name", "ai_agent_name", "message_trace_uid", "metadata_product_name"],
 "application_lifecycle": ["time", "class_uid", "activity_id", "app_name", "app_version", "app_url_string", "attestation_list_authority_uid", "attestation_list_signatures_state_id", "actor_user_name", "actor_process_name", "device_hostname", "metadata_product_name"],
}
if __name__ == "__main__":
    bad = 0
    for cls, cols in TABLES.items():
        for c in cols:
            r = resolve(cls, c)
            print(f"{'OK  ' if r else 'FAIL'} {cls}.{c} -> {r}")
            bad += r is None
    print("FAILED", bad); sys.exit(1 if bad else 0)
