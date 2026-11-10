[
  {
    "row_id": "d3f:RemoteTerminalSession",
    "grade": "generic",
    "ocsf_object": "session",
    "ocsf_class_uid": null,
    "ocsf_field": "session.terminal",
    "rationale": "OCSF provides the generic session object representing authenticated sessions. While session includes terminal and is_remote attributes, it lacks a dedicated object or discriminator field denoting a remote terminal session."
  },
  {
    "row_id": "d3f:EventLog",
    "grade": "direct",
    "ocsf_object": "metadata",
    "ocsf_class_uid": null,
    "ocsf_field": "metadata.log_name",
    "rationale": "OCSF provides the dedicated metadata.log_name field to identify the specific event log (e.g., System, Security, Application) in which the event was recorded."
  },
  {
    "row_id": "d3f:AccessToken",
    "grade": "direct",
    "ocsf_object": "authentication_token",
    "ocsf_class_uid": null,
    "ocsf_field": "authentication_token.uid",
    "rationale": "OCSF directly provides the authentication_token object (extending token) to represent authentication and access tokens, using uid as its identifier."
  },
  {
    "row_id": "d3f:InitScript",
    "grade": "generic",
    "ocsf_object": "script",
    "ocsf_class_uid": null,
    "ocsf_field": "script.name",
    "rationale": "OCSF provides the generic script object representing executable scripts, but lacks a dedicated init script object or field denoting that the script serves an initialization role."
  },
  {
    "row_id": "d3f:Credential",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF lacks an object or dedicated field for credentials. While reference fields like credential_uid and specific factor types exist, no schema element denotes the general credential artifact itself."
  },
  {
    "row_id": "d3f:CollaborativeSoftware",
    "grade": "generic",
    "ocsf_object": "application",
    "ocsf_class_uid": null,
    "ocsf_field": "application.name",
    "rationale": "OCSF provides the generic application object representing software applications, but lacks a dedicated collaborative software object or field denoting groupware or collaboration functionality."
  },
  {
    "row_id": "d3f:MACAddress",
    "grade": "direct",
    "ocsf_object": "network_interface",
    "ocsf_class_uid": null,
    "ocsf_field": "network_interface.mac",
    "rationale": "OCSF provides the dedicated mac field on the network_interface object to record the Media Access Control address assigned to a network interface controller."
  },
  {
    "row_id": "d3f:DatabaseQuery",
    "grade": "direct",
    "ocsf_object": "query_info",
    "ocsf_class_uid": null,
    "ocsf_field": "query_info.query_string",
    "rationale": "OCSF defines the query_info object with the dedicated query_string field to record SQL or other database query statements executed against a datastore."
  },
  {
    "row_id": "d3f:ShellCommand",
    "grade": "direct",
    "ocsf_object": "process",
    "ocsf_class_uid": null,
    "ocsf_field": "process.cmd_line",
    "rationale": "OCSF provides the dedicated cmd_line attribute on the process object to record the command-line directive or shell command executed."
  },
  {
    "row_id": "d3f:Email",
    "grade": "direct",
    "ocsf_object": "email",
    "ocsf_class_uid": null,
    "ocsf_field": "email.message_uid",
    "rationale": "OCSF defines a dedicated email object representing email messages and their metadata, with message_uid as the unique message identifier."
  }
]
