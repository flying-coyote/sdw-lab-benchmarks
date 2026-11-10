[
  {
    "row_id": "d3f:GroupPolicy",
    "grade": "generic",
    "ocsf_object": "policy",
    "ocsf_class_uid": null,
    "ocsf_field": "policy.name",
    "rationale": "OCSF defines the generic policy object, but lacks a dedicated object or field for Windows Group Policy."
  },
  {
    "row_id": "d3f:ProcessSegment",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF lacks an object or field representing process memory segments such as heap, stack, or data segments."
  },
  {
    "row_id": "d3f:CloudInstanceMetadata",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF lacks an object or field for cloud instance metadata or configuration; cloud defines the hosting environment."
  },
  {
    "row_id": "d3f:Metadata",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF metadata defines event logging metadata rather than the digital artifact of metadata describing other information; no target object exists."
  },
  {
    "row_id": "d3f:CreateProcess",
    "grade": "event",
    "ocsf_object": null,
    "ocsf_class_uid": 1007,
    "ocsf_field": null,
    "rationale": "CreateProcess is an occurrent system call mapped to OCSF process_activity (class UID 1007), which captures process launch activities."
  },
  {
    "row_id": "d3f:Application",
    "grade": "direct",
    "ocsf_object": "application",
    "ocsf_class_uid": null,
    "ocsf_field": "application.name",
    "rationale": "OCSF directly defines the application object to represent an application."
  },
  {
    "row_id": "d3f:ExecutableFile",
    "grade": "generic",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.name",
    "rationale": "OCSF provides the parent file object, but lacks a dedicated object or attribute distinguishing executable files from other files."
  },
  {
    "row_id": "d3f:SoftwarePackage",
    "grade": "direct",
    "ocsf_object": "package",
    "ocsf_class_uid": null,
    "ocsf_field": "package.name",
    "rationale": "OCSF directly defines the package object representing a software package."
  },
  {
    "row_id": "d3f:IntrusionDetectionSystem",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF lacks a dedicated object or field for an intrusion detection system, and does not model the parent DigitalInformationBearer."
  },
  {
    "row_id": "d3f:CodeRepository",
    "grade": "generic",
    "ocsf_object": "database",
    "ocsf_class_uid": null,
    "ocsf_field": "database.name",
    "rationale": "OCSF models the parent database object, but lacks a dedicated object or field distinguishing code repositories."
  }
]
