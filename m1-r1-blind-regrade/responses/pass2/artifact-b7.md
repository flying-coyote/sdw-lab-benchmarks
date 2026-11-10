[
  {
    "row_id": "d3f:ApplicationConfiguration",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF lacks an object or dedicated field for application configuration, and does not define its parent kind ConfigurationResource."
  },
  {
    "row_id": "d3f:WebAPIResource",
    "grade": "generic",
    "ocsf_object": "web_resource",
    "ocsf_class_uid": null,
    "ocsf_field": "web_resource.type",
    "rationale": "OCSF provides the parent kind web_resource, but lacks a dedicated object or specific field distinguishing a web API resource."
  },
  {
    "row_id": "d3f:ConfigurationResource",
    "grade": "generic",
    "ocsf_object": "resource_details",
    "ocsf_class_uid": null,
    "ocsf_field": "resource_details.type",
    "rationale": "OCSF provides the parent kind resource_details for generic resources, but lacks a dedicated object or field for configuration resources."
  },
  {
    "row_id": "d3f:WebResource",
    "grade": "direct",
    "ocsf_object": "web_resource",
    "ocsf_class_uid": null,
    "ocsf_field": "web_resource.url_string",
    "rationale": "OCSF defines the web_resource object specifically representing resources identified by a URI and accessed via web protocols."
  },
  {
    "row_id": "d3f:DatabaseRecord",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF has no object or field representing an individual database record or its parent Record kind."
  },
  {
    "row_id": "d3f:SoftwareRepository",
    "grade": "proxy",
    "ocsf_object": "package",
    "ocsf_class_uid": null,
    "ocsf_field": "package.src_url",
    "rationale": "OCSF has no object for a software repository; only carrier fields like package.src_url can reference the repository location."
  },
  {
    "row_id": "d3f:Application",
    "grade": "direct",
    "ocsf_object": "application",
    "ocsf_class_uid": null,
    "ocsf_field": "application.name",
    "rationale": "OCSF defines a dedicated application object representing an application."
  },
  {
    "row_id": "d3f:MoveFile",
    "grade": "event",
    "ocsf_object": null,
    "ocsf_class_uid": 1001,
    "ocsf_field": null,
    "rationale": "MoveFile is a system call occurrent recorded by OCSF file_activity (class UID 1001) via its activity_id."
  },
  {
    "row_id": "d3f:DomainRegistration",
    "grade": "direct",
    "ocsf_object": "whois",
    "ocsf_class_uid": null,
    "ocsf_field": "whois.domain",
    "rationale": "OCSF defines the whois object specifically representing domain registration data from WHOIS/RDAP services."
  },
  {
    "row_id": "d3f:ExecutableFile",
    "grade": "generic",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.type",
    "rationale": "OCSF provides the parent kind file object, but lacks a dedicated object or field distinguishing executable files."
  }
]
