[
  {
    "row_id": "d3f:InboundInternetMailTraffic",
    "grade": "generic",
    "ocsf_object": "network_traffic",
    "ocsf_class_uid": null,
    "ocsf_field": "network_traffic.bytes",
    "rationale": "OCSF provides the parent network_traffic object, but lacks a dedicated object or field denoting inbound internet mail traffic."
  },
  {
    "row_id": "d3f:DigitalText",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF 1.9.0 has no object or dedicated field denoting digital text or digital media."
  },
  {
    "row_id": "d3f:ConfigurationResource",
    "grade": "generic",
    "ocsf_object": "resource_details",
    "ocsf_class_uid": null,
    "ocsf_field": "resource_details.type",
    "rationale": "OCSF defines the generic parent resource_details object, but lacks a dedicated object or field specifically denoting configuration resources."
  },
  {
    "row_id": "d3f:WindowsRegistryKey",
    "grade": "direct",
    "ocsf_object": "reg_key",
    "ocsf_class_uid": null,
    "ocsf_field": "reg_key.path",
    "rationale": "OCSF provides the dedicated reg_key object to represent Windows registry keys, with the path attribute identifying the key."
  },
  {
    "row_id": "d3f:Database",
    "grade": "direct",
    "ocsf_object": "database",
    "ocsf_class_uid": null,
    "ocsf_field": "database.name",
    "rationale": "OCSF defines a dedicated database object for datastore services and collections of data, with the name attribute identifying it."
  },
  {
    "row_id": "d3f:IntrusionDetectionSystem",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF 1.9.0 does not define an object or dedicated field representing an intrusion detection system."
  },
  {
    "row_id": "d3f:ProcessEnvironmentVariable",
    "grade": "direct",
    "ocsf_object": "environment_variable",
    "ocsf_class_uid": null,
    "ocsf_field": "environment_variable.name",
    "rationale": "OCSF provides the dedicated environment_variable object to represent process environment variables, with attributes including name and value."
  },
  {
    "row_id": "d3f:ArchiveFile",
    "grade": "generic",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.type",
    "rationale": "OCSF provides the parent file object, but does not have a dedicated archive file object or field identifying archive files."
  },
  {
    "row_id": "d3f:InboundInternetNetworkTraffic",
    "grade": "generic",
    "ocsf_object": "network_traffic",
    "ocsf_class_uid": null,
    "ocsf_field": "network_traffic.bytes",
    "rationale": "OCSF provides the parent network_traffic object, but lacks a dedicated object or field specifying inbound internet network traffic."
  }
]
