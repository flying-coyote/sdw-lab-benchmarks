[
  {
    "row_id": "d3f:SoftwareRepository",
    "grade": "proxy",
    "ocsf_object": "url",
    "ocsf_class_uid": null,
    "ocsf_field": "url.url_string",
    "rationale": "OCSF lacks an object for software repositories; a software repository can only be referenced by a carrier URL field such as url.url_string."
  },
  {
    "row_id": "d3f:GroupPolicy",
    "grade": "generic",
    "ocsf_object": "policy",
    "ocsf_class_uid": null,
    "ocsf_field": "policy.name",
    "rationale": "OCSF provides the generic policy object representing applicable policies, but lacks a dedicated object or attribute specifically denoting Windows Group Policy."
  },
  {
    "row_id": "d3f:WebAPIResource",
    "grade": "generic",
    "ocsf_object": "web_resource",
    "ocsf_class_uid": null,
    "ocsf_field": "web_resource.url_string",
    "rationale": "OCSF provides the generic parent web_resource object, but lacks a dedicated object or field distinguishing Web API resources from other web resources."
  },
  {
    "row_id": "d3f:Application",
    "grade": "direct",
    "ocsf_object": "application",
    "ocsf_class_uid": null,
    "ocsf_field": "application.name",
    "rationale": "OCSF defines a direct application object describing an inventoried application or program, with fields such as application.name."
  },
  {
    "row_id": "d3f:CodeRepository",
    "grade": "generic",
    "ocsf_object": "database",
    "ocsf_class_uid": null,
    "ocsf_field": "database.name",
    "rationale": "OCSF provides the parent database object for datastores, but lacks a dedicated code repository object or field to distinguish source code repositories."
  },
  {
    "row_id": "d3f:ProxyServer",
    "grade": "direct",
    "ocsf_object": "network_proxy",
    "ocsf_class_uid": null,
    "ocsf_field": "network_proxy.hostname",
    "rationale": "OCSF defines a dedicated network_proxy object that directly represents a proxy server intermediary between clients and servers."
  },
  {
    "row_id": "d3f:OutboundInternetNetworkTraffic",
    "grade": "generic",
    "ocsf_object": "network_traffic",
    "ocsf_class_uid": null,
    "ocsf_field": "network_traffic.bytes_out",
    "rationale": "OCSF provides the parent network_traffic object, but does not distinguish outbound internet network traffic through a dedicated object or specific traffic attribute."
  },
  {
    "row_id": "d3f:ApplicationConfiguration",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF lacks an object or dedicated field for application configuration settings or parameters, and no carrier field applies."
  },
  {
    "row_id": "d3f:ArtifactServer",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF lacks an object or dedicated field for an artifact server or web server, and its parent kind does not exist in the schema."
  },
  {
    "row_id": "d3f:CommandHistoryLog",
    "grade": "proxy",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.path",
    "rationale": "OCSF lacks an object for command history logs or event logs; shell command history is recorded only via a file path carrier field (file.path)."
  }
]
