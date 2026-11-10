```json
[
  {
    "row_id": "d3f:DefaultUserAccount",
    "grade": "generic",
    "ocsf_object": "account",
    "ocsf_class_uid": null,
    "ocsf_field": "account.type",
    "rationale": "OCSF provides the parent account object, but lacks a dedicated field or boolean indicating that an account is a built-in or default system account."
  },
  {
    "row_id": "d3f:CollaborativeSoftware",
    "grade": "generic",
    "ocsf_object": "application",
    "ocsf_class_uid": null,
    "ocsf_field": "application.type",
    "rationale": "OCSF models software applications via the application object, but has no specific field or type classifying groupware or collaborative software."
  },
  {
    "row_id": "d3f:CommandHistoryLogFile",
    "grade": "generic",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.type",
    "rationale": "OCSF models files via the file object, but lacks a dedicated field or classification distinguishing command history log files from other files."
  },
  {
    "row_id": "d3f:ProxyServer",
    "grade": "direct",
    "ocsf_object": "network_proxy",
    "ocsf_class_uid": null,
    "ocsf_field": "network_proxy.hostname",
    "rationale": "The network_proxy object directly describes a proxy server acting as an intermediary between a client and server."
  },
  {
    "row_id": "d3f:URL",
    "grade": "direct",
    "ocsf_object": "url",
    "ocsf_class_uid": null,
    "ocsf_field": "url.url_string",
    "rationale": "The url object directly represents a Uniform Resource Locator, with url_string recording the full URL address."
  },
  {
    "row_id": "d3f:CloudUserAccount",
    "grade": "generic",
    "ocsf_object": "account",
    "ocsf_class_uid": null,
    "ocsf_field": "account.type",
    "rationale": "OCSF provides the parent account object, but lacks a dedicated subkind field defining a local cloud user account on a host."
  },
  {
    "row_id": "d3f:InitScript",
    "grade": "generic",
    "ocsf_object": "script",
    "ocsf_class_uid": null,
    "ocsf_field": "script.type",
    "rationale": "OCSF represents executable scripts via the script object, but lacks a field denoting that the script is an initialization script."
  },
  {
    "row_id": "d3f:DatabaseQuery",
    "grade": "direct",
    "ocsf_object": "query_info",
    "ocsf_class_uid": null,
    "ocsf_field": "query_info.query_string",
    "rationale": "The query_info object directly represents datastore queries, with query_string holding the database query text."
  },
  {
    "row_id": "d3f:CreateProcess",
    "grade": "event",
    "ocsf_object": null,
    "ocsf_class_uid": 1007,
    "ocsf_field": null,
    "rationale": "Create Process is a system call occurrent representing process creation, recorded as the process_activity event class (uid 1007) with a launch activity ID."
  },
  {
    "row_id": "d3f:JobSchedule",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF lacks an object or field representing a job schedule specification or timing plan; job and trigger objects capture task execution state rather than the schedule."
  }
]
```
