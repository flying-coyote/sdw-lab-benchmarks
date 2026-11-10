[
  {
    "row_id": "d3f:CloudStorage",
    "grade": "direct",
    "ocsf_object": "databucket",
    "ocsf_class_uid": null,
    "ocsf_field": "databucket.name",
    "rationale": "OCSF defines the databucket object to represent cloud datastores and storage containers, identified by databucket.name."
  },
  {
    "row_id": "d3f:PersonalComputer",
    "grade": "generic",
    "ocsf_object": "device",
    "ocsf_class_uid": null,
    "ocsf_field": "device.type_id",
    "rationale": "OCSF provides the parent device object, but lacks a dedicated type denoting a personal computer. The attribute device.is_personal denotes BYOD ownership rather than the PC form factor."
  },
  {
    "row_id": "d3f:URL",
    "grade": "direct",
    "ocsf_object": "url",
    "ocsf_class_uid": null,
    "ocsf_field": "url.url_string",
    "rationale": "OCSF defines a dedicated url object whose url_string attribute directly records the Uniform Resource Locator."
  },
  {
    "row_id": "d3f:DocumentFile",
    "grade": "generic",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.type_id",
    "rationale": "OCSF provides the parent file object, but lacks a dedicated object or attribute denoting a document file specifically."
  },
  {
    "row_id": "d3f:Database",
    "grade": "direct",
    "ocsf_object": "database",
    "ocsf_class_uid": null,
    "ocsf_field": "database.name",
    "rationale": "OCSF defines a dedicated database object representing an organized collection of data, identified by database.name."
  },
  {
    "row_id": "d3f:OperatingSystemExecutableFile",
    "grade": "generic",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.is_system",
    "rationale": "OCSF provides the generic file object. While file.is_system indicates system files, OCSF lacks a dedicated field distinguishing operating system executables from other system files."
  },
  {
    "row_id": "d3f:AccessToken",
    "grade": "direct",
    "ocsf_object": "token",
    "ocsf_class_uid": null,
    "ocsf_field": "token.type_id",
    "rationale": "OCSF defines the token object to represent authentication credentials and tokens across contexts, with token.type_id specifically denoting an access token."
  },
  {
    "row_id": "d3f:Process",
    "grade": "direct",
    "ocsf_object": "process",
    "ocsf_class_uid": null,
    "ocsf_field": "process.name",
    "rationale": "OCSF defines a dedicated process object that directly represents a running instance of a program, identified by process.name."
  },
  {
    "row_id": "d3f:ApplicationConfiguration",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF 1.9.0 does not define an object or dedicated field representing application configuration settings or initial parameters."
  },
  {
    "row_id": "d3f:FileSystemMetadata",
    "grade": "direct",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.attributes",
    "rationale": "OCSF defines the file object specifically as the metadata associated with a file, providing dedicated attributes like file.attributes to capture file system metadata."
  }
]
