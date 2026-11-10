[
  {
    "row_id": "d3f:Metadata",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "Mapping by meaning (Discipline 1), D3FEND Metadata refers to data describing target digital artifacts. OCSF's metadata object captures event logging envelope details, not target artifact metadata; OCSF has no object or field for generic artifact metadata."
  },
  {
    "row_id": "d3f:WebFileResource",
    "grade": "proxy",
    "ocsf_object": "url",
    "ocsf_class_uid": null,
    "ocsf_field": "url.url_string",
    "rationale": "OCSF has no dedicated object for a web file resource; it is only referenced through a carrier field holding a URL, such as url.url_string."
  },
  {
    "row_id": "d3f:EventLog",
    "grade": "direct",
    "ocsf_object": "metadata",
    "ocsf_class_uid": null,
    "ocsf_field": "metadata.log_name",
    "rationale": "OCSF provides the dedicated field metadata.log_name to record the specific event log (such as Security or System) in which events are recorded."
  },
  {
    "row_id": "d3f:CloudConfiguration",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF 1.9.0 has no object or field for cloud configuration settings; the cloud object only records environment context such as provider and region."
  },
  {
    "row_id": "d3f:ConfigurationFile",
    "grade": "generic",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.type",
    "rationale": "OCSF provides the parent file object, but lacks a dedicated field or enum value to distinguish a configuration file from any other file."
  },
  {
    "row_id": "d3f:ServiceApplication",
    "grade": "direct",
    "ocsf_object": "service",
    "ocsf_class_uid": null,
    "ocsf_field": "service.name",
    "rationale": "OCSF defines the service object, which directly denotes a service application providing software functionalities to multiple clients."
  },
  {
    "row_id": "d3f:Server",
    "grade": "direct",
    "ocsf_object": "device",
    "ocsf_class_uid": null,
    "ocsf_field": "device.type_id",
    "rationale": "OCSF's device object represents a host, and the dedicated type_id field specifically identifies the device type as a server."
  },
  {
    "row_id": "d3f:RemoteSession",
    "grade": "direct",
    "ocsf_object": "session",
    "ocsf_class_uid": null,
    "ocsf_field": "session.is_remote",
    "rationale": "OCSF defines the session object with a dedicated boolean field is_remote that explicitly denotes whether a session is remote."
  },
  {
    "row_id": "d3f:DigitalMedia",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF 1.9.0 does not define an object or field representing communication media or digital media formats."
  },
  {
    "row_id": "d3f:UserAccount",
    "grade": "direct",
    "ocsf_object": "account",
    "ocsf_class_uid": null,
    "ocsf_field": "account.name",
    "rationale": "OCSF's account object directly represents an account used for authentication and authorization, with fields such as name and type."
  }
]
