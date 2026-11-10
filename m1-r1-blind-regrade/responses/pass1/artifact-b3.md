[
  {
    "row_id": "d3f:SystemConfigurationDatabase",
    "grade": "generic",
    "ocsf_object": "database",
    "ocsf_class_uid": null,
    "ocsf_field": "database.type",
    "rationale": "OCSF defines the generic database datastore object, but lacks a dedicated object or attribute for system configuration databases."
  },
  {
    "row_id": "d3f:GetRunningProcesses",
    "grade": "event",
    "ocsf_object": null,
    "ocsf_class_uid": 5015,
    "ocsf_field": null,
    "rationale": "As a system call occurrent querying running processes, this artifact maps to OCSF's process_query event class (UID 5015)."
  },
  {
    "row_id": "d3f:DefaultUserAccount",
    "grade": "generic",
    "ocsf_object": "user",
    "ocsf_class_uid": null,
    "ocsf_field": "user.type",
    "rationale": "OCSF provides the parent user object, but lacks a dedicated attribute or object to denote default or built-in user accounts."
  },
  {
    "row_id": "d3f:DigitalMedia",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF 1.9.0 has no object, field, or event class denoting digital communication media."
  },
  {
    "row_id": "d3f:Host",
    "grade": "direct",
    "ocsf_object": "device",
    "ocsf_class_uid": null,
    "ocsf_field": "device.hostname",
    "rationale": "OCSF directly defines the device object as an addressable computer system or host, with hostname providing the host identifier."
  },
  {
    "row_id": "d3f:DigitalMessage",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF lacks a general digital message object, only providing specialized protocol structures like email without a generic application-layer message representation."
  },
  {
    "row_id": "d3f:Repository",
    "grade": "proxy",
    "ocsf_object": "url",
    "ocsf_class_uid": null,
    "ocsf_field": "url.url_string",
    "rationale": "OCSF lacks a dedicated repository object; storage repositories for code or files are referenced only through carrier fields like URLs."
  },
  {
    "row_id": "d3f:SoftwarePackage",
    "grade": "direct",
    "ocsf_object": "package",
    "ocsf_class_uid": null,
    "ocsf_field": "package.name",
    "rationale": "OCSF contains a dedicated package object representing software packages, with name identifying the package."
  },
  {
    "row_id": "d3f:ConfigurationFile",
    "grade": "generic",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.type",
    "rationale": "OCSF provides the parent file object, but contains no field or type distinguishing configuration files from general files."
  },
  {
    "row_id": "d3f:Server",
    "grade": "direct",
    "ocsf_object": "device",
    "ocsf_class_uid": null,
    "ocsf_field": "device.type",
    "rationale": "OCSF models servers using the device object with the dedicated type field indicating a server host."
  }
]
