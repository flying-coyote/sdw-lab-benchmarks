[
  {
    "row_id": "d3f:Log",
    "grade": "proxy",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.path",
    "rationale": "OCSF lacks an object representing a log (logger represents the logging device; log_name is a label). A log stored on a filesystem can only be referenced through a carrier field such as file.path."
  },
  {
    "row_id": "d3f:Email",
    "grade": "direct",
    "ocsf_object": "email",
    "ocsf_class_uid": null,
    "ocsf_field": "email.message_uid",
    "rationale": "The OCSF email object directly represents an email message, with email.message_uid uniquely identifying the email message document."
  },
  {
    "row_id": "d3f:FileSystemMetadata",
    "grade": "direct",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.attributes",
    "rationale": "The OCSF file object directly represents the metadata associated with a file in a computer system, and file.attributes captures specific file system attribute flags."
  },
  {
    "row_id": "d3f:CloudStorage",
    "grade": "direct",
    "ocsf_object": "databucket",
    "ocsf_class_uid": null,
    "ocsf_field": "databucket.name",
    "rationale": "The OCSF databucket object directly represents cloud storage containers (such as S3 buckets) held within a computing cloud, identified by databucket.name."
  },
  {
    "row_id": "d3f:SoftwareLibrary",
    "grade": "direct",
    "ocsf_object": "package",
    "ocsf_class_uid": null,
    "ocsf_field": "package.name",
    "rationale": "The OCSF package object directly denotes software packages and libraries used to build software products, with package.name identifying the library."
  },
  {
    "row_id": "d3f:CreateFile",
    "grade": "event",
    "ocsf_object": null,
    "ocsf_class_uid": 1001,
    "ocsf_field": null,
    "rationale": "CreateFile is a system-call occurrent recorded in OCSF as a File System Activity event (class UID 1001), where creation is indicated by the activity_id."
  },
  {
    "row_id": "d3f:CloudInstanceMetadata",
    "grade": "proxy",
    "ocsf_object": "url",
    "ocsf_class_uid": null,
    "ocsf_field": "url.url_string",
    "rationale": "OCSF lacks an object for cloud instance metadata; access to the instance metadata service (IMDS) can only be referenced through a carrier field such as url.url_string."
  },
  {
    "row_id": "d3f:DigitalText",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF has no object or dedicated field for generic digital text or digital media. Written text is only stored within context-specific string fields rather than as an independent artifact."
  },
  {
    "row_id": "d3f:DigitalMessage",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF has no generic object for an application-layer digital message, nor does it define the parent DigitalInformationBearer kind. OCSF models specific communication types individually."
  },
  {
    "row_id": "d3f:InboundInternetMailTraffic",
    "grade": "generic",
    "ocsf_object": "network_traffic",
    "ocsf_class_uid": null,
    "ocsf_field": "network_traffic.bytes_in",
    "rationale": "OCSF provides the parent kind network_traffic, but what specializes it as inbound internet mail traffic (mail protocol, external boundary) is not an attribute of the network_traffic object itself."
  }
]
