[
  {
    "row_id": "d3f:AuthenticationService",
    "grade": "direct",
    "ocsf_object": "idp",
    "ocsf_class_uid": null,
    "ocsf_field": "idp.name",
    "rationale": "OCSF idp object represents an identity provider responsible for offering authentication services to applications, denoting the same kind as an authentication service."
  },
  {
    "row_id": "d3f:GetRunningProcesses",
    "grade": "event",
    "ocsf_object": null,
    "ocsf_class_uid": 5015,
    "ocsf_field": null,
    "rationale": "Get Running Processes is a system call occurrent mapped to OCSF process_query event class (UID 5015), which reports information about running processes."
  },
  {
    "row_id": "d3f:ArchiveFile",
    "grade": "generic",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.name",
    "rationale": "OCSF has the parent file object, but lacks a dedicated object or field to distinguish an archive file from other files."
  },
  {
    "row_id": "d3f:ProcessEnvironmentVariable",
    "grade": "direct",
    "ocsf_object": "environment_variable",
    "ocsf_class_uid": null,
    "ocsf_field": "environment_variable.name",
    "rationale": "OCSF provides a dedicated environment_variable object (and process.environment_variables field) that directly records environment variables in which a process runs."
  },
  {
    "row_id": "d3f:CommandHistoryLog",
    "grade": "proxy",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.path",
    "rationale": "OCSF lacks an object for command history logs; shell command history files can only be referenced indirectly via a file carrier field such as file.path."
  },
  {
    "row_id": "d3f:MACAddress",
    "grade": "direct",
    "ocsf_object": "network_interface",
    "ocsf_class_uid": null,
    "ocsf_field": "network_interface.mac",
    "rationale": "OCSF network_interface object contains a dedicated mac attribute representing the MAC address of a network interface controller."
  },
  {
    "row_id": "d3f:Host",
    "grade": "direct",
    "ocsf_object": "device",
    "ocsf_class_uid": null,
    "ocsf_field": "device.hostname",
    "rationale": "OCSF device object explicitly represents an addressable computer system or host connected to a network, with hostname denoting the host."
  },
  {
    "row_id": "d3f:DocumentFile",
    "grade": "generic",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.name",
    "rationale": "OCSF defines the parent file object, but lacks a dedicated object or field distinguishing a document file from other files."
  },
  {
    "row_id": "d3f:ExecutableScript",
    "grade": "direct",
    "ocsf_object": "script",
    "ocsf_class_uid": null,
    "ocsf_field": "script.name",
    "rationale": "OCSF script object directly represents a script or command executed by a shell or interpreter, denoting the same kind as an executable script."
  },
  {
    "row_id": "d3f:Database",
    "grade": "direct",
    "ocsf_object": "database",
    "ocsf_class_uid": null,
    "ocsf_field": "database.name",
    "rationale": "OCSF database object directly represents databases containing organized collections of data, denoting the same kind as the D3FEND database artifact."
  }
]
