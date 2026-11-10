[
  {
    "row_id": "d3f:CreateFile",
    "grade": "event",
    "ocsf_object": null,
    "ocsf_class_uid": 1001,
    "ocsf_field": null,
    "rationale": "CreateFile is a system call occurrent. OCSF records file creation as an event under the file_activity event class (UID 1001) via an activity_id rather than a standalone object."
  },
  {
    "row_id": "d3f:UserAccount",
    "grade": "direct",
    "ocsf_object": "account",
    "ocsf_class_uid": null,
    "ocsf_field": "account.name",
    "rationale": "The OCSF account object directly denotes a user or system account, with account.name identifying the specific account within an application or system."
  },
  {
    "row_id": "d3f:ProcessEnvironmentVariable",
    "grade": "direct",
    "ocsf_object": "environment_variable",
    "ocsf_class_uid": null,
    "ocsf_field": "environment_variable.name",
    "rationale": "OCSF directly models process environment variables via the environment_variable object (environment_variable.name), which are also recorded on processes under process.environment_variables."
  },
  {
    "row_id": "d3f:DigitalText",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF 1.9.0 does not define an object, dedicated field, or parent class representing generic digital text or digital media content."
  },
  {
    "row_id": "d3f:SoftwareRepository",
    "grade": "proxy",
    "ocsf_object": "package",
    "ocsf_class_uid": null,
    "ocsf_field": "package.src_url",
    "rationale": "OCSF lacks a software repository object; repositories can only be referenced indirectly through carrier URL fields such as package.src_url or package.package_manager_url."
  },
  {
    "row_id": "d3f:Email",
    "grade": "direct",
    "ocsf_object": "email",
    "ocsf_class_uid": null,
    "ocsf_field": "email.message_uid",
    "rationale": "The OCSF email object directly represents an email message, with email.message_uid providing the unique message identifier."
  },
  {
    "row_id": "d3f:Server",
    "grade": "generic",
    "ocsf_object": "device",
    "ocsf_class_uid": null,
    "ocsf_field": "device.type",
    "rationale": "OCSF provides the parent kind Host via the device object, but lacks a dedicated server object, classifying device roles generically through device.type."
  },
  {
    "row_id": "d3f:CommandHistoryLog",
    "grade": "proxy",
    "ocsf_object": "file",
    "ocsf_class_uid": null,
    "ocsf_field": "file.path",
    "rationale": "OCSF has no dedicated command history log object; the shell history log file can only be referenced indirectly via a carrier path field like file.path."
  },
  {
    "row_id": "d3f:ShellCommand",
    "grade": "direct",
    "ocsf_object": "process",
    "ocsf_class_uid": null,
    "ocsf_field": "process.cmd_line",
    "rationale": "OCSF directly records shell command invocations via the dedicated process.cmd_line field, as well as the script object (script.script_content) representing shell commands."
  }
]
