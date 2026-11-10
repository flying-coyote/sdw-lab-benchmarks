[
  {
    "row_id": "d3f:Software",
    "grade": "direct",
    "ocsf_object": "product",
    "ocsf_class_uid": null,
    "ocsf_field": "product.name",
    "rationale": "OCSF represents software using the product object, which captures software characteristics including name, vendor, and version."
  },
  {
    "row_id": "d3f:DatabaseRecord",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF defines database and table objects, but does not provide an object or field representing an individual database record or row."
  },
  {
    "row_id": "d3f:ExecutableBinary",
    "grade": "generic",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.type",
    "rationale": "OCSF provides the parent file object, but lacks a dedicated object or field to distinguish executable binaries from other file types."
  },
  {
    "row_id": "d3f:OutboundInternetWebTraffic",
    "grade": "generic",
    "ocsf_object": "network_traffic",
    "ocsf_class_uid": null,
    "ocsf_field": "network_traffic.bytes_out",
    "rationale": "OCSF provides the parent network_traffic object (with bytes_out), but lacks a dedicated object or field to specify that the traffic is outbound internet web traffic."
  },
  {
    "row_id": "d3f:OutboundInternetNetworkTraffic",
    "grade": "generic",
    "ocsf_object": "network_traffic",
    "ocsf_class_uid": null,
    "ocsf_field": "network_traffic.bytes_out",
    "rationale": "OCSF has the parent network_traffic object, capturing outgoing traffic volume via bytes_out, but lacks a dedicated object or field specifically denoting outbound internet traffic."
  },
  {
    "row_id": "d3f:WebFileResource",
    "grade": "generic",
    "ocsf_object": "web_resource",
    "ocsf_class_uid": null,
    "ocsf_field": "web_resource.url_string",
    "rationale": "OCSF provides the parent web_resource object, but does not have a dedicated field or object distinguishing file resources from other web resources."
  },
  {
    "row_id": "d3f:DigitalIdentity",
    "grade": "direct",
    "ocsf_object": "account",
    "ocsf_class_uid": null,
    "ocsf_field": "account.uid",
    "rationale": "OCSF's account object directly represents a digital identity in a system or service, with account.uid uniquely identifying the subject."
  },
  {
    "row_id": "d3f:NetworkTraffic",
    "grade": "direct",
    "ocsf_object": "network_traffic",
    "ocsf_class_uid": null,
    "ocsf_field": "network_traffic.bytes",
    "rationale": "OCSF's network_traffic object directly represents network traffic, with the bytes attribute measuring the amount of data moving across the network."
  },
  {
    "row_id": "d3f:DigitalMessage",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF lacks an object or field representing a generic digital message, only providing specialized objects for specific message protocols like email."
  },
  {
    "row_id": "d3f:WebResource",
    "grade": "direct",
    "ocsf_object": "web_resource",
    "ocsf_class_uid": null,
    "ocsf_field": "web_resource.url_string",
    "rationale": "OCSF's web_resource object directly represents a web resource, with url_string identifying the resource via its URI."
  }
]
