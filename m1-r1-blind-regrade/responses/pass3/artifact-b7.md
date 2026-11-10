[
  {
    "row_id": "d3f:DefaultUserAccount",
    "grade": "generic",
    "ocsf_object": "account",
    "ocsf_class_uid": null,
    "ocsf_field": "account.type",
    "rationale": "OCSF defines the parent account object but lacks a dedicated field or value to indicate that an account is a built-in or default account; account.type only provides generic account typing."
  },
  {
    "row_id": "d3f:RemoteTerminalSession",
    "grade": "generic",
    "ocsf_object": "session",
    "ocsf_class_uid": null,
    "ocsf_field": "session.terminal",
    "rationale": "OCSF provides the generic session object with terminal and is_remote attributes, but lacks a dedicated object or field denoting a remote terminal session specifically."
  },
  {
    "row_id": "d3f:ExecutableScript",
    "grade": "direct",
    "ocsf_object": "script",
    "ocsf_class_uid": null,
    "ocsf_field": "script.name",
    "rationale": "OCSF directly defines the script object to describe a script or command executed by an interpreter or shell, denoting the same kind as an executable script."
  },
  {
    "row_id": "d3f:DatabaseQuery",
    "grade": "direct",
    "ocsf_object": "query_info",
    "ocsf_class_uid": null,
    "ocsf_field": "query_info.query_string",
    "rationale": "OCSF directly defines the query_info object for datastore access queries, with query_info.query_string capturing the specific query text (such as SQL) executed against a database."
  },
  {
    "row_id": "d3f:MoveFile",
    "grade": "event",
    "ocsf_object": null,
    "ocsf_class_uid": 1001,
    "ocsf_field": null,
    "rationale": "MoveFile is an occurrent (system call) recorded in OCSF as the file_activity event class (UID 1001) using an activity_id for rename/move, rather than as a standalone object."
  },
  {
    "row_id": "d3f:Repository",
    "grade": "proxy",
    "ocsf_object": "url",
    "ocsf_class_uid": null,
    "ocsf_field": "url.url_string",
    "rationale": "OCSF has no object for a code or file repository; a repository is referenced only through carrier fields such as url.url_string or a file path."
  },
  {
    "row_id": "d3f:ArtifactServer",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF 1.9.0 has no object or field representing an artifact server or web server; neither the artifact nor its parent kind is modeled in the schema."
  },
  {
    "row_id": "d3f:ServiceApplication",
    "grade": "direct",
    "ocsf_object": "service",
    "ocsf_class_uid": null,
    "ocsf_field": "service.name",
    "rationale": "OCSF directly provides the service object to describe software services that provide functionalities to clients, denoting the same kind as a service application."
  },
  {
    "row_id": "d3f:RemoteSession",
    "grade": "direct",
    "ocsf_object": "session",
    "ocsf_class_uid": null,
    "ocsf_field": "session.is_remote",
    "rationale": "OCSF's session object includes the dedicated boolean field is_remote, which directly indicates whether an authenticated session is a remote login session."
  },
  {
    "row_id": "d3f:CloudConfiguration",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF 1.9.0 has no object or field representing cloud configuration settings; the cloud object only captures environment metadata like provider, region, and account."
  }
]
