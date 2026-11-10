"""Check catalogue for T4-interdiction: which checks each control carries, which table each runs on, its
unit, and the hand-written SQL for the aggregate and join checks (D1, D6a, D6c, D7). Single-event checks
are Sigma rules in rules/ compiled by pySigma's sqlite backend in run.py. Hand SQL uses only constructs
SQLite 3.45 and DuckDB 1.5 share: GROUP BY, HAVING, COUNT(DISTINCT), integer `%` for tumbling hour
buckets (`time - (time % 3600000)`), substr/instr/replace. "Any 1 h window" in PREREGISTRATION.md is
implemented as tumbling hour buckets, an interpretation recorded in RESULTS.md."""

HOUR = 3_600_000
CEIL_CALLS = 500        # D1 / D7 per-identity calls per hour bucket
CEIL_TOKENS = 200_000   # D7 per-identity response tokens per hour bucket
CEIL_ACCOUNTS = 10      # D6c distinct accounts per source IP per hour bucket

# control -> list of (check id, kind, table, unit, source). kind: sigma | sql. unit: event | identity | ip | message
CHECKS = {
    "AML.M0019": [("E1", "sigma", "api_activity", "event", "E1_unauthenticated_model_api.yml"),
                  ("D1", "sql", "api_activity", "identity", "D1")],
    "AML.M0043": [("E2.api", "sigma", "api_activity", "event", "E2_agent_unbrokered_create_api.yml"),
                  ("E2.account", "sigma", "account_change", "event", "E2_agent_unbrokered_create_account.yml")],
    "AML.M0005": [("E3.file", "sigma", "file_activity", "event", "E3_unapproved_at_rest_file.yml"),
                  ("E3.datastore", "sigma", "datastore_activity", "event", "E3_unapproved_at_rest_datastore.yml")],
    "AML.M0011": [("E4", "sigma", "module_activity", "event", "E4_module_outside_allowlisted_roots.yml"),
                  ("E4b", "sigma", "module_activity", "event", "E4b_deserialization_imports_outside_allowlist.yml")],
    "AML.M0020": [("E5a", "sigma", "api_activity", "event", "E5a_prompt_injection_blocklist.yml"),
                  ("E5b", "sigma", "api_activity", "event", "E5b_destructive_tool_request.yml"),
                  ("E5c", "sigma", "api_activity", "event", "E5c_hidden_html_comment_instruction.yml")],
    "AML.M0024": [("D6a", "sql", "api_activity+email_activity", "message", "D6a"),
                  ("D6b", "sigma", "api_activity", "event", "D6b_destructive_action_executed.yml"),
                  ("D6c", "sql", "api_activity", "ip", "D6c")],
    "AML.M0040": [("D7", "sql", "api_activity", "identity", "D7")],
    "AML.M0013": [("E8a.process", "sigma", "process_activity", "event", "E8a_unsigned_process.yml"),
                  ("E8a.module", "sigma", "module_activity", "event", "E8a_unsigned_module.yml"),
                  ("E8b", "sigma", "application_lifecycle", "event", "E8b_install_without_pinned_attestation.yml"),
                  ("E8c", "sigma", "file_activity", "event", "E8c_unsigned_model_artifact_load.yml")],
}

# Rules whose planted text is partly mixed-case, for the labelled supplementary case-folded variant (H5)
CASE_SENSITIVE_RULES = ["E5a", "E5b", "E5c"]

# ---- hand SQL. Each returns rows (entity_key, ...) ; run.py maps entities back to event_uids. ----
SQL = {
    # M0019 "monitor production model queries ... usage policies": per identity, calls per hour bucket above the ceiling
    "D1": f"""
        SELECT actor_user_name AS entity, (time - (time % {HOUR})) AS bucket, COUNT(*) AS n
        FROM api_activity
        WHERE metadata_product_name = 'model-gateway' AND api_operation = 'chat.completions' AND actor_user_name IS NOT NULL
        GROUP BY actor_user_name, (time - (time % {HOUR}))
        HAVING COUNT(*) > {CEIL_CALLS}""",
    # M0040 "suspected extraction activity": per identity, calls or response tokens per hour bucket above the ceilings
    "D7": f"""
        SELECT actor_user_name AS entity, (time - (time % {HOUR})) AS bucket, COUNT(*) AS n, SUM(message_context_total_tokens) AS toks
        FROM api_activity
        WHERE metadata_product_name = 'model-gateway' AND api_operation = 'chat.completions' AND actor_user_name IS NOT NULL
        GROUP BY actor_user_name, (time - (time % {HOUR}))
        HAVING COUNT(*) > {CEIL_CALLS} OR SUM(message_context_total_tokens) > {CEIL_TOKENS}""",
    # M0024 "coordinated behavior across accounts and access pathways": distinct accounts per source IP per hour bucket
    "D6c": f"""
        SELECT src_endpoint_ip AS entity, (time - (time % {HOUR})) AS bucket, COUNT(DISTINCT actor_user_name) AS n
        FROM api_activity
        WHERE metadata_product_name = 'model-gateway' AND api_operation = 'chat.completions' AND actor_user_name IS NOT NULL
        GROUP BY src_endpoint_ip, (time - (time % {HOUR}))
        HAVING COUNT(DISTINCT actor_user_name) >= {CEIL_ACCOUNTS}""",
    # M0024 "distinguish requested actions from those actually executed, using independent service records":
    # the agent's mail-tool request joined to the provider's delivery record on the trace id; alert when the
    # provider saw a BCC the request did not carry. Returns the trace id and both event uids.
    "D6a": """
        SELECT e.message_trace_uid AS entity, a.event_uid AS req_uid, e.event_uid AS rec_uid
        FROM api_activity a
        JOIN email_activity e
          ON e.message_trace_uid = replace(substr(a.api_request_data, instr(a.api_request_data, '"trace": "') + 10), '"}', '')
        WHERE a.metadata_product_name = 'agent-runtime' AND a.api_operation = 'postmark.sendEmail'
          AND e.metadata_product_name = 'mail-provider'
          AND e.email_bcc IS NOT NULL AND a.api_request_data NOT LIKE '%"bcc"%'""",
}

# entity -> owned events, for mapping an alerted identity / IP back to event uids on the table the check reads
OWNED = {
    "identity": "SELECT event_uid FROM api_activity WHERE metadata_product_name = 'model-gateway' AND actor_user_name = ?",
    "ip": "SELECT event_uid FROM api_activity WHERE metadata_product_name = 'model-gateway' AND src_endpoint_ip = ?",
}
