[
  {
    "row_id": "d3f:Process",
    "grade": "direct",
    "ocsf_object": "process",
    "ocsf_class_uid": null,
    "ocsf_field": "process.name",
    "rationale": "OCSF defines the process object to describe a running instance of a program, directly denoting the same kind as the D3FEND Process artifact."
  },
  {
    "row_id": "d3f:URL",
    "grade": "direct",
    "ocsf_object": "url",
    "ocsf_class_uid": null,
    "ocsf_field": "url.url_string",
    "rationale": "OCSF defines the url object with attribute url_string to represent Uniform Resource Locators, directly denoting the same kind as the D3FEND URL artifact."
  },
  {
    "row_id": "d3f:AccessControlConfiguration",
    "grade": "generic",
    "ocsf_object": "policy",
    "ocsf_class_uid": null,
    "ocsf_field": "policy.name",
    "rationale": "OCSF provides the generic policy object to represent policies and configurations, but lacks a dedicated object or field specifically denoting access control configurations granting permissions to users for objects."
  },
  {
    "row_id": "d3f:UserAccount",
    "grade": "direct",
    "ocsf_object": "user",
    "ocsf_class_uid": null,
    "ocsf_field": "user.name",
    "rationale": "OCSF defines the user object to describe a user or security principal, directly denoting the same kind as the D3FEND User Account artifact."
  },
  {
    "row_id": "d3f:ExecutableFile",
    "grade": "generic",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.type",
    "rationale": "OCSF provides the parent file object, but lacks a dedicated object or specific field distinguishing executable files from other file types."
  },
  {
    "row_id": "d3f:PrivateKey",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF 1.9.0 does not define an object or dedicated field representing private cryptographic keys."
  },
  {
    "row_id": "d3f:CloudUserAccount",
    "grade": "generic",
    "ocsf_object": "user",
    "ocsf_class_uid": null,
    "ocsf_field": "user.type",
    "rationale": "OCSF provides the parent user object, but lacks a dedicated object or field distinguishing cloud user accounts from general user accounts."
  },
  {
    "row_id": "d3f:ExecutableScript",
    "grade": "direct",
    "ocsf_object": "script",
    "ocsf_class_uid": null,
    "ocsf_field": "script.name",
    "rationale": "OCSF defines the script object to describe an executable script or command executed by an interpreter or shell, directly matching the D3FEND Executable Script artifact."
  },
  {
    "row_id": "d3f:OperatingSystemExecutableFile",
    "grade": "generic",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.is_system",
    "rationale": "OCSF provides the parent file object with an is_system attribute, but lacks a dedicated object or field identifying the system file specifically as an executable."
  },
  {
    "row_id": "d3f:NetworkTraffic",
    "grade": "direct",
    "ocsf_object": "network_traffic",
    "ocsf_class_uid": null,
    "ocsf_field": "network_traffic.bytes",
    "rationale": "OCSF defines the network_traffic object to describe characteristics and metrics of data moving across a network, directly matching the D3FEND Network Traffic artifact."
  }
]
