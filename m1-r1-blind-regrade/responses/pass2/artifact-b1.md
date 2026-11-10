[
  {
    "row_id": "d3f:File",
    "grade": "direct",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.name",
    "rationale": "OCSF directly defines the `file` object to represent metadata of files stored on a computer system, identified by attributes like `name` and `path`."
  },
  {
    "row_id": "d3f:Software",
    "grade": "direct",
    "ocsf_object": "product",
    "ocsf_class_uid": null,
    "ocsf_field": "product.name",
    "rationale": "OCSF defines `product` to describe characteristics of software products, directly representing software by meaning via attributes like `name` and `cpe_name`."
  },
  {
    "row_id": "d3f:ArtifactServer",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF has no dedicated object or field for artifact servers or web servers, and does not model repository server infrastructure."
  },
  {
    "row_id": "d3f:PrivateKey",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF contains no object or field for private keys. Telemetry schemas intentionally omit private cryptographic keys to avoid exposing sensitive secrets."
  },
  {
    "row_id": "d3f:PersonalComputer",
    "grade": "generic",
    "ocsf_object": "device",
    "ocsf_class_uid": null,
    "ocsf_field": "device.type",
    "rationale": "OCSF provides the parent object `device` for host computer systems, but lacks a dedicated type or field denoting a personal computer."
  },
  {
    "row_id": "d3f:Repository",
    "grade": "proxy",
    "ocsf_object": "url",
    "ocsf_class_uid": null,
    "ocsf_field": "url.url_string",
    "rationale": "OCSF lacks an object for code or artifact repositories; they can only be referenced indirectly through carrier fields such as `url.url_string`."
  },
  {
    "row_id": "d3f:InboundInternetNetworkTraffic",
    "grade": "generic",
    "ocsf_object": "network_traffic",
    "ocsf_class_uid": null,
    "ocsf_field": "network_traffic.bytes_in",
    "rationale": "OCSF provides the parent kind `network_traffic` for traffic volume metrics, but lacks a field distinguishing traffic as specifically internet-originated."
  },
  {
    "row_id": "d3f:ShellCommand",
    "grade": "direct",
    "ocsf_object": "process",
    "ocsf_class_uid": null,
    "ocsf_field": "process.cmd_line",
    "rationale": "OCSF provides the dedicated field `process.cmd_line` to record command-line directives, and also models shell commands via `script.script_content`."
  },
  {
    "row_id": "d3f:RemoteShellCommand",
    "grade": "generic",
    "ocsf_object": "process",
    "ocsf_class_uid": null,
    "ocsf_field": "process.cmd_line",
    "rationale": "OCSF captures commands via the parent kind `process.cmd_line`, but lacks an object or dedicated field indicating that execution was remotely initiated."
  },
  {
    "row_id": "d3f:ProcessSegment",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF lacks any object or field representing process memory space partitions such as heap, data, or stack segments."
  }
]
