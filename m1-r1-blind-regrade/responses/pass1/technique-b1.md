[
  {
    "row_id": "AML.T0000.003",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "Adversaries query external scan databases like Shodan or Censys without directly interacting with the victim target, producing no victim-side telemetry or observable events in OCSF."
  },
  {
    "row_id": "AML.T0011.002",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF 1.9.0 lacks any object, event class, or field for observing AI agent tool invocations, tool execution logic, or poisoned tool interactions on the victim side."
  },
  {
    "row_id": "AML.T0054",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF 1.9.0 lacks an event class or dedicated object/field for recording LLM jailbreak attempts, adversarial prompt injections, or safety alignment overrides on the victim system."
  },
  {
    "row_id": "AML.T0016.002",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "Adversaries searching for and obtaining generative AI models occurs entirely on adversary-controlled infrastructure during resource development, generating no victim-side telemetry in OCSF."
  },
  {
    "row_id": "AML.T0016.003",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "Obtaining exploits is an adversary-side resource development technique conducted prior to an attack, leaving no observable trace or telemetry on victim systems in OCSF."
  },
  {
    "row_id": "AML.T0116",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "Autonomous reconnaissance planning and agentic execution take place on adversary infrastructure; victim telemetry cannot observe or record whether incoming reconnaissance originates from an autonomous AI agent."
  },
  {
    "row_id": "AML.T0025",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "Exfiltration via cyber means is an attack technique; OCSF records network traffic generically but lacks a dedicated class or field directly recording data exfiltration itself."
  },
  {
    "row_id": "AML.T0048.000",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "Financial harm is an impact outcome involving monetary or asset loss; OCSF 1.9.0 does not define any financial loss objects, classes, or attributes."
  },
  {
    "row_id": "AML.T0031",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "OCSF 1.9.0 contains no object, metric, or event class to monitor AI model performance degradation, accuracy loss, or model integrity erosion over time."
  },
  {
    "row_id": "AML.T0011.001",
    "grade": "none",
    "ocsf_object": null,
    "ocsf_class_uid": null,
    "ocsf_field": null,
    "rationale": "Developing and introducing malicious software packages is not directly recorded by OCSF 1.9.0; package inventory objects describe metadata but do not record malicious package techniques."
  }
]
