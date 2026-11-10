[
  {
    "row_id": "d3f:SoftwarePackage",
    "grade": "direct",
    "ocsf_object": "package",
    "ocsf_class_uid": null,
    "ocsf_field": "package.name",
    "rationale": "OCSF directly defines the `package` object to describe details about a software package, including its name and version."
  },
  {
    "row_id": "d3f:WindowsRegistryKey",
    "grade": "direct",
    "ocsf_object": "reg_key",
    "ocsf_class_uid": null,
    "ocsf_field": "reg_key.path",
    "rationale": "OCSF directly defines the `reg_key` object to describe a Windows registry key, identified by its path."
  },
  {
    "row_id": "d3f:ExecutableBinary",
    "grade": "generic",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.type",
    "rationale": "OCSF provides the parent `file` object, but lacks a dedicated object or field to distinguish an executable binary from other file types."
  },
  {
    "row_id": "d3f:RemoteTerminalSession",
    "grade": "generic",
    "ocsf_object": "session",
    "ocsf_class_uid": null,
    "ocsf_field": "session.terminal",
    "rationale": "OCSF provides the parent `session` object with `terminal` and `is_remote` attributes, but lacks a dedicated object or field specifically denoting a remote terminal session."
  },
  {
    "row_id": "d3f:AccessControlConfiguration",
    "grade": "generic",
    "ocsf_object": "policy",
    "ocsf_class_uid": null,
    "ocsf_field": "policy.name",
    "rationale": "OCSF provides the parent `policy` object to describe applicable policies, but lacks a dedicated object or field specifically denoting access control configurations."
  },
  {
    "row_id": "d3f:OutboundInternetWebTraffic",
    "grade": "generic",
    "ocsf_object": "network_traffic",
    "ocsf_class_uid": null,
    "ocsf_field": "network_traffic.bytes_out",
    "rationale": "OCSF provides the parent `network_traffic` object, but lacks fields to specify that traffic is outbound, internet-facing, and using a web protocol."
  },
  {
    "row_id": "d3f:ServiceApplicationProcess",
    "grade": "generic",
    "ocsf_object": "process",
    "ocsf_class_uid": null,
    "ocsf_field": "process.hosted_services",
    "rationale": "OCSF provides the parent `process` object, but lacks a dedicated object or field classifying a process specifically as a service application process."
  },
  {
    "row_id": "d3f:DigitalIdentity",
    "grade": "direct",
    "ocsf_object": "account",
    "ocsf_class_uid": null,
    "ocsf_field": "account.uid",
    "rationale": "OCSF directly defines the `account` object to represent the unique representation or account of a subject within a system or application, identified by `uid`."
  },
  {
    "row_id": "d3f:OperatingSystemExecutableFile",
    "grade": "generic",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.is_system",
    "rationale": "OCSF provides the parent `file` object with `is_system` for operating system files, but lacks a dedicated field distinguishing OS executable files from other OS files."
  },
  {
    "row_id": "d3f:Process",
    "grade": "direct",
    "ocsf_object": "process",
    "ocsf_class_uid": null,
    "ocsf_field": "process.pid",
    "rationale": "OCSF directly defines the `process` object to describe a running instance of a launched program, identified by `pid`."
  }
]
