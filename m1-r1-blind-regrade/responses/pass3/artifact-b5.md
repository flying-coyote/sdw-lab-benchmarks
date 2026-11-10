[
  {
    "row_id": "d3f:ProxyServer",
    "grade": "direct",
    "ocsf_object": "network_proxy",
    "ocsf_class_uid": null,
    "ocsf_field": "network_proxy.hostname",
    "rationale": "OCSF defines the network_proxy object specifically to describe a proxy server acting as an intermediary between clients and servers."
  },
  {
    "row_id": "d3f:Command",
    "grade": "direct",
    "ocsf_object": "process",
    "ocsf_class_uid": null,
    "ocsf_field": "process.cmd_line",
    "rationale": "OCSF provides the dedicated field process.cmd_line to directly record the command directive issued to execute a process."
  },
  {
    "row_id": "d3f:ConfigurationResource",
    "grade": "generic",
    "ocsf_object": "resource_details",
    "ocsf_class_uid": null,
    "ocsf_field": "resource_details.type",
    "rationale": "OCSF provides resource_details for generic resources (the parent kind), but lacks a dedicated object or field distinguishing a configuration resource."
  },
  {
    "row_id": "d3f:RemoteShellCommand",
    "grade": "generic",
    "ocsf_object": "process",
    "ocsf_class_uid": null,
    "ocsf_field": "process.cmd_line",
    "rationale": "OCSF models commands via the parent kind process.cmd_line, but lacks a dedicated object or field indicating that the command was executed remotely."
  },
  {
    "row_id": "d3f:Log",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF models individual event records rather than a log container (a historical record of events). No object represents a log; metadata.log_name merely names the source log."
  },
  {
    "row_id": "d3f:InboundInternetNetworkTraffic",
    "grade": "generic",
    "ocsf_object": "network_traffic",
    "ocsf_class_uid": null,
    "ocsf_field": "network_traffic.bytes",
    "rationale": "OCSF provides the parent kind network_traffic, but what makes the traffic specifically inbound internet traffic is not an attribute of the network_traffic object."
  },
  {
    "row_id": "d3f:ConfigurationFile",
    "grade": "generic",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.name",
    "rationale": "OCSF defines the generic parent object file, but lacks a dedicated object or attribute specifying that the file is a configuration file."
  },
  {
    "row_id": "d3f:WindowsRegistryKey",
    "grade": "direct",
    "ocsf_object": "reg_key",
    "ocsf_class_uid": null,
    "ocsf_field": "reg_key.path",
    "rationale": "OCSF directly defines the reg_key object to represent a Windows registry key, including its path and security descriptor."
  },
  {
    "row_id": "d3f:WebAPIResource",
    "grade": "generic",
    "ocsf_object": "web_resource",
    "ocsf_class_uid": null,
    "ocsf_field": "web_resource.url_string",
    "rationale": "OCSF provides the parent kind web_resource, but lacks a dedicated object or field specific to a Web API resource."
  },
  {
    "row_id": "d3f:CloudUserAccount",
    "grade": "generic",
    "ocsf_object": "account",
    "ocsf_class_uid": null,
    "ocsf_field": "account.name",
    "rationale": "OCSF provides the parent kind account, but lacks a dedicated object or field identifying the account specifically as a cloud user account."
  }
]
