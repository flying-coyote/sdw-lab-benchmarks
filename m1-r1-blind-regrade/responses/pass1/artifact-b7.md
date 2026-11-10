[
  {
    "row_id": "d3f:Log",
    "grade": "proxy",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.path",
    "rationale": "OCSF lacks a dedicated object for a log; when maintained on a system, it can only be referenced via carrier fields such as file.path."
  },
  {
    "row_id": "d3f:ServiceApplicationProcess",
    "grade": "generic",
    "ocsf_object": "process",
    "ocsf_class_uid": null,
    "ocsf_field": "process.name",
    "rationale": "OCSF provides the parent kind process for running programs, but lacks a dedicated field to classify a process specifically as a service application process."
  },
  {
    "row_id": "d3f:DigitalIdentity",
    "grade": "direct",
    "ocsf_object": "user",
    "ocsf_class_uid": null,
    "ocsf_field": "user.uid",
    "rationale": "OCSF defines the user object to describe a security principal or user representing the subject's digital identity in online transactions, directly matching the artifact."
  },
  {
    "row_id": "d3f:File",
    "grade": "direct",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.name",
    "rationale": "OCSF defines the file object to represent metadata associated with a file stored in a computer system, directly matching the artifact."
  },
  {
    "row_id": "d3f:DomainRegistration",
    "grade": "direct",
    "ocsf_object": "whois",
    "ocsf_class_uid": null,
    "ocsf_field": "whois.domain",
    "rationale": "OCSF defines the whois object to record domain registration data, including registrar, domain, and contact details, directly matching the artifact."
  },
  {
    "row_id": "d3f:JobSchedule",
    "grade": "direct",
    "ocsf_object": "job",
    "ocsf_class_uid": null,
    "ocsf_field": "job.name",
    "rationale": "OCSF defines the job object to record scheduled jobs and tasks, including their actions, triggers, and execution times, directly denoting the artifact."
  },
  {
    "row_id": "d3f:Software",
    "grade": "direct",
    "ocsf_object": "product",
    "ocsf_class_uid": null,
    "ocsf_field": "product.name",
    "rationale": "OCSF defines the product object to describe software products, directly representing computer software with attributes like name, vendor, and version."
  },
  {
    "row_id": "d3f:CloudStorage",
    "grade": "direct",
    "ocsf_object": "databucket",
    "ocsf_class_uid": null,
    "ocsf_field": "databucket.name",
    "rationale": "OCSF defines the databucket object for containers holding partitioned data in cloud storage environments (e.g., S3 or GCS), directly representing cloud storage."
  },
  {
    "row_id": "d3f:CloudInstanceMetadata",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF has no object or field representing cloud instance metadata or configuration (such as security groups, public keys, or user data initialization scripts)."
  },
  {
    "row_id": "d3f:OutboundInternetWebTraffic",
    "grade": "generic",
    "ocsf_object": "network_traffic",
    "ocsf_class_uid": null,
    "ocsf_field": "network_traffic.bytes",
    "rationale": "OCSF provides the parent kind network_traffic, but lacks fields within that object to denote that traffic is outbound, internet-scoped, or web-protocol specific."
  }
]
