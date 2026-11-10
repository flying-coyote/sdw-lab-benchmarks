[
  {
    "row_id": "d3f:PersonalComputer",
    "grade": "generic",
    "ocsf_object": "device",
    "ocsf_class_uid": null,
    "ocsf_field": "device.type",
    "rationale": "OCSF provides the parent device object, but lacks a dedicated type or field distinguishing a personal computer from other computing systems."
  },
  {
    "row_id": "d3f:Metadata",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF metadata describes event record envelope telemetry rather than the monitored digital artifact itself. OCSF has no object or field recording arbitrary digital information metadata."
  },
  {
    "row_id": "d3f:CloudConfiguration",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF lacks an object or dedicated field representing cloud service instance configuration settings or parameters."
  },
  {
    "row_id": "d3f:AuthenticationService",
    "grade": "direct",
    "ocsf_object": "idp",
    "ocsf_class_uid": null,
    "ocsf_field": "idp.name",
    "rationale": "OCSF idp directly denotes an identity provider service responsible for offering authentication services to applications."
  },
  {
    "row_id": "d3f:Command",
    "grade": "direct",
    "ocsf_object": "process",
    "ocsf_class_uid": null,
    "ocsf_field": "process.cmd_line",
    "rationale": "OCSF process.cmd_line is a dedicated field that directly records the directive or command line executed by the system."
  },
  {
    "row_id": "d3f:CommandHistoryLogFile",
    "grade": "proxy",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.path",
    "rationale": "OCSF has no dedicated object for a command history log file; it can only be identified and referenced through the carrier field file.path."
  },
  {
    "row_id": "d3f:CreateProcess",
    "grade": "event",
    "ocsf_object": null,
    "ocsf_class_uid": 1007,
    "ocsf_field": null,
    "rationale": "The artifact is an occurrent (system call). OCSF records process creation via event class process_activity (class_uid 1007)."
  },
  {
    "row_id": "d3f:ServiceApplication",
    "grade": "direct",
    "ocsf_object": "service",
    "ocsf_class_uid": null,
    "ocsf_field": "service.name",
    "rationale": "OCSF provides the service object to describe software functionalities and services provided to clients."
  },
  {
    "row_id": "d3f:CreateFile",
    "grade": "event",
    "ocsf_object": null,
    "ocsf_class_uid": 1001,
    "ocsf_field": null,
    "rationale": "The artifact is an occurrent (system call). OCSF captures file creation through the file_activity event class (class_uid 1001)."
  },
  {
    "row_id": "d3f:WebResource",
    "grade": "direct",
    "ocsf_object": "web_resource",
    "ocsf_class_uid": null,
    "ocsf_field": "web_resource.url_string",
    "rationale": "OCSF web_resource directly represents resources identified by URIs and accessed over web protocols, with url_string recording the URI."
  }
]
