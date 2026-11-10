[
  {
    "row_id": "d3f:FileSystemMetadata",
    "grade": "direct",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.attributes",
    "rationale": "OCSF's file object represents metadata associated with a file, and file.attributes directly records file system attributes."
  },
  {
    "row_id": "d3f:DocumentFile",
    "grade": "generic",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.type",
    "rationale": "OCSF provides the parent file object, but lacks a specific object or dedicated field for document files."
  },
  {
    "row_id": "d3f:ProcessSegment",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF does not define an object, parent object, or field to represent process memory segments such as heap or stack."
  },
  {
    "row_id": "d3f:RemoteSession",
    "grade": "direct",
    "ocsf_object": "session",
    "ocsf_class_uid": null,
    "ocsf_field": "session.is_remote",
    "rationale": "OCSF's session object includes the dedicated boolean attribute is_remote to indicate that an authenticated session is remote."
  },
  {
    "row_id": "d3f:RemoteShellCommand",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF lacks an object, parent kind, or field representing remote commands or commands transmitted over a network for remote execution."
  },
  {
    "row_id": "d3f:DatabaseRecord",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF defines database and table objects, but has no object, parent kind, or field representing an individual database record or row."
  },
  {
    "row_id": "d3f:ExecutableBinary",
    "grade": "generic",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.type",
    "rationale": "OCSF provides the parent file object, but lacks a specific object or dedicated field distinguishing executable binaries from other files."
  },
  {
    "row_id": "d3f:MoveFile",
    "grade": "event",
    "ocsf_object": null,
    "ocsf_class_uid": 1001,
    "ocsf_field": null,
    "rationale": "Move File is a system-call occurrent; OCSF models file move and rename operations within the file_activity event class (uid 1001) via activity_id."
  },
  {
    "row_id": "d3f:WebFileResource",
    "grade": "proxy",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.url",
    "rationale": "OCSF lacks an object for web file resources; the carrier field file.url holds the URL reference to the remotely accessible file."
  },
  {
    "row_id": "d3f:SoftwareLibrary",
    "grade": "generic",
    "ocsf_object": "package",
    "ocsf_class_uid": null,
    "ocsf_field": "package.type",
    "rationale": "OCSF provides the parent package object representing software packages, but has no dedicated object or specific field defining a software library."
  }
]
