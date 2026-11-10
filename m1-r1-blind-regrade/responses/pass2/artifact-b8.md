[
  {
    "row_id": "d3f:Credential",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF lacks an object or dedicated field representing general credentials (such as passwords, physical tokens, or biometrics); specific digital token objects exist, but no generic credential entity is defined."
  },
  {
    "row_id": "d3f:Command",
    "grade": "direct",
    "ocsf_object": "process",
    "ocsf_class_uid": null,
    "ocsf_field": "process.cmd_line",
    "rationale": "OCSF process.cmd_line is a dedicated field that directly records the command directive issued to execute a process or computation."
  },
  {
    "row_id": "d3f:IntrusionDetectionSystem",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF lacks an object or dedicated field for an intrusion detection system, and does not model its generic parent entity."
  },
  {
    "row_id": "d3f:OutboundInternetNetworkTraffic",
    "grade": "generic",
    "ocsf_object": "network_traffic",
    "ocsf_class_uid": null,
    "ocsf_field": "network_traffic.bytes",
    "rationale": "OCSF provides the parent network_traffic object, but lacks a dedicated field denoting that the traffic is destined for the external internet."
  },
  {
    "row_id": "d3f:CodeRepository",
    "grade": "generic",
    "ocsf_object": "database",
    "ocsf_class_uid": null,
    "ocsf_field": "database.name",
    "rationale": "OCSF provides the parent database object, but lacks a dedicated object or specific field denoting a source code repository."
  },
  {
    "row_id": "d3f:NetworkTraffic",
    "grade": "direct",
    "ocsf_object": "network_traffic",
    "ocsf_class_uid": null,
    "ocsf_field": "network_traffic.bytes",
    "rationale": "OCSF network_traffic object directly denotes the volume and characteristics of data moving across a network over a time period."
  },
  {
    "row_id": "d3f:SystemConfigurationDatabase",
    "grade": "generic",
    "ocsf_object": "database",
    "ocsf_class_uid": null,
    "ocsf_field": "database.name",
    "rationale": "OCSF provides the parent database object, but lacks a dedicated object or field identifying it specifically as a system configuration database."
  },
  {
    "row_id": "d3f:GroupPolicy",
    "grade": "generic",
    "ocsf_object": "policy",
    "ocsf_class_uid": null,
    "ocsf_field": "policy.name",
    "rationale": "OCSF provides the parent policy object, but lacks a dedicated object or specific field for Windows Group Policy."
  },
  {
    "row_id": "d3f:AccessToken",
    "grade": "direct",
    "ocsf_object": "authentication_token",
    "ocsf_class_uid": null,
    "ocsf_field": "authentication_token.uid",
    "rationale": "OCSF authentication_token object directly represents standardized authentication and access tokens conforming to established authentication protocols."
  }
]
