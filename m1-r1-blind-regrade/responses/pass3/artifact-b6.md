[
  {
    "row_id": "d3f:InboundInternetMailTraffic",
    "grade": "generic",
    "ocsf_object": "network_traffic",
    "ocsf_class_uid": null,
    "ocsf_field": "network_traffic.bytes_in",
    "rationale": "OCSF provides the parent object network_traffic for traffic metrics, but lacks fields to specify that the traffic is inbound, internet-facing, or using an email protocol."
  },
  {
    "row_id": "d3f:SystemConfigurationDatabase",
    "grade": "generic",
    "ocsf_object": "database",
    "ocsf_class_uid": null,
    "ocsf_field": "database.type",
    "rationale": "OCSF defines the generic parent object database, but lacks a dedicated object or field indicating that the database holds system configuration data."
  },
  {
    "row_id": "d3f:Credential",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF lacks an object or dedicated field representing credentials broadly. Related objects like token or certificate only cover specific subtypes, and the parent kind DigitalInformationBearer is absent from OCSF."
  },
  {
    "row_id": "d3f:JobSchedule",
    "grade": "direct",
    "ocsf_object": "job",
    "ocsf_class_uid": null,
    "ocsf_field": "job.name",
    "rationale": "OCSF directly represents scheduled jobs and tasks via the job object, capturing task commands, triggers, and schedule specifications in fields such as job.name and job.job_triggers."
  },
  {
    "row_id": "d3f:GetRunningProcesses",
    "grade": "event",
    "ocsf_object": null,
    "ocsf_class_uid": 5015,
    "ocsf_field": null,
    "rationale": "As a system-call occurrent, this is recorded in OCSF as an event class rather than an object; class 5015 (process_query) specifically reports discovered running processes."
  },
  {
    "row_id": "d3f:File",
    "grade": "direct",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.name",
    "rationale": "OCSF directly models files stored in computer systems via the file object, with file.name identifying the file."
  },
  {
    "row_id": "d3f:InitScript",
    "grade": "generic",
    "ocsf_object": "script",
    "ocsf_class_uid": null,
    "ocsf_field": "script.name",
    "rationale": "OCSF provides the generic parent object script for executable scripts, but lacks a dedicated object or field to designate a script specifically as an initialization or boot script."
  },
  {
    "row_id": "d3f:Host",
    "grade": "direct",
    "ocsf_object": "device",
    "ocsf_class_uid": null,
    "ocsf_field": "device.hostname",
    "rationale": "The OCSF device object explicitly represents an addressable computer system or host connected to a network, identified by device.hostname."
  },
  {
    "row_id": "d3f:EventLog",
    "grade": "direct",
    "ocsf_object": "metadata",
    "ocsf_class_uid": null,
    "ocsf_field": "metadata.log_name",
    "rationale": "OCSF directly identifies the specific event log using the dedicated field metadata.log_name (or logger.log_name) on the event."
  },
  {
    "row_id": "d3f:DomainRegistration",
    "grade": "direct",
    "ocsf_object": "whois",
    "ocsf_class_uid": null,
    "ocsf_field": "whois.domain",
    "rationale": "OCSF directly models domain registration data via the whois object, which captures WHOIS and RDAP domain registration records, identified by whois.domain."
  }
]
