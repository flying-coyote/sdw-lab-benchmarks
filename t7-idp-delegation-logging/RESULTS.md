---
type: benchmark-results
title: "T7 results: does an identity provider's audit trail record an agent delegation chain?"
created: 2026-11-10
evidence_tier: B (first-party, single host, one IdP product at one version, synthetic realm; no LLM arm)
---

# T7 results: IdP delegation logging across an OAuth 2.0 token-exchange chain

**Pre-registration:** `PREREGISTRATION.md`, sha256 `f95931e86b33294284ac58c989f62bb6dd4e9cced4f70a85122cb7177d6e8ef6`,
frozen 2026-11-10T01:05:35Z, **frozen by agent before run; not owner-reviewed.** One dated amendment after the run
(analysis-side only; nothing re-run). Harness and analysis hashes in `results/freeze.txt`.

**Rig stamp (methodology §7b; latencies are incidental here).** Beelink, AMD Ryzen 7 5800H, WSL2 kernel
6.6.87.2-microsoft-standard-WSL2, Windows power plan not readable from the guest. Run 2026-11-10T01:05:35Z to
01:07:34Z. Keycloak 26.8.1 (`quay.io/keycloak/keycloak@sha256:3f3c5f8e…7332`, created 2026-10-31) on Docker 29.5.3,
`start-dev`, dev-file H2, `--cpus=4 --memory=2g`, JVM `ActiveProcessorCount=4`; harness Python 3.12.3, PyJWT 2.15.1,
cryptography 50.0.2, under `taskset -c 10-13 nice -n 10`. Clock: chrony running; `chronyc tracking` read 0.633 s
*slow* of NTP before the run and 0.0000027 s fast after it, so chrony corrected the wall clock forward (stepped or slewed; 0.63 s over two minutes is within its slew rate)
during the run, and the wall-clock stamps in the Keycloak log and the event `time` fields may be compressed by up
to 0.63 s. A forward correction preserves event order within a session, which is what H3 and H4 depend on. Every
duration below is `time.perf_counter_ns` (monotonic) and unaffected. **Isolation was not met:** other benches shared
the host and the 1-minute load average was 18.4 to 19.4 throughout, so timings were taken under contention and are
reported only to show the harness was not the bottleneck.

## Headline

The discriminating question was whether a Keycloak token-exchange event carries a parent pointer, and the answer is
*half*: every `TOKEN_EXCHANGE` event names the **client** the subject token was issued to (`subject_token_client_id`)
and the **id of the token it issued** (`token_id`, equal to the new token's `jti`), but never the subject token's own
id, so the chain is explicit at client granularity and only implicit (session plus time order) at token granularity.
That half matters in exactly the case agents produce: when one user token is exchanged by three agent instances in
one session, the events say "agent-b exchanged a token from agent-a" three times with no identifier linking any hop 2 to its
hop 1, and the pre-registered nearest-earlier rule attributed 5 of 15 correctly. A scope-matching heuristic would
have scored 15 of 15 on these events, but only because the plants gave each chain a distinct scope set, which real
traffic does not guarantee. Keycloak's RFC 8693 delegation preview puts the
actor into both the token (`act`) and the event (`actor`, `actor_id`, `actor_type`), which is the audit trail the
spec promises, and in the same move drops the session identifier from both, because the delegated token is issued
in a transient session; it also stops at one actor hop. In single-chain sessions R7's `reacquire` escalation is detectable from Keycloak
events alone, because each event carries the effective `scope` of the token it issued and the hops share a
`sessionId`, and the root-only check misses it 5 of 5 times as it did over R7's synthetic rows. R7's `new` class
never reached a token: Keycloak silently dropped the `data:admin` scope the user had no role for, and **no event
field records what was asked for**, so the attempt is invisible unless the `downscope-assertion-grant-enforcer`
policy is on, in which case the refusal is logged with the attempted scope inside the `client_policy_error_detail` string
but with no `userId`, `sessionId`, `username`, `subject_token_client_id`, `audience` or `scope` field, so the
attempt cannot be attributed to a user or a chain from the event alone (the delegation-feature refusals in arm D do
carry `userId` and `subject_token_client_id`; the gap is specific to the client-policy refusal path). Enabling and disabling that policy, a security-control change, produced
no admin event on REST or in the log, and the server's admin-event `resourceType` enum (40 values) has no
client-policy type, so on the surfaces checked (REST and the log at INFO; DEBUG was not checked) this looks like an event kind Keycloak does not have rather than one it failed to emit. On OCSF 1.9.0 the events-only producer fills `delegation.uid`, `issuer_uid`
and `created_time` on every hop and `parent_uid` on none; `scopes` and `audience` exist only on OCSF main; and the
refusal events cannot form a valid `authentication` record because the class requires `user` and the IdP omits it.

## Hypotheses

| | Pre-registered prediction | Measured | Verdict |
|---|---|---|---|
| H1 no parent pointer | no event names the subject token's `jti` or its issuing client | 0 of 78 (S) and 0 of 15 (D) hops had the subject `jti` in any event field; **72 of 72 (S) successful exchange events and 15 of 15 (D) exchange events (9 successful plus 6 refusals) carried `subject_token_client_id`** equal to the subject token's `azp`, while the 6 arm S enforcer refusals carry none; `token_id` equalled the issued `jti` in 72/72 and 9/9 | **Half wrong.** Client-level parent pointer present; token-level absent. Linkage grade: EXPLICIT (client), IMPLICIT (token). |
| H2 claims | arm S: no `act`/`may_act`; arm D: T0 `may_act{sub, client_id}`, T1 `act`, no `sid` | S: 0 of 101 tokens carried `act` or `may_act`, all carried `sid`, `azp` moved to the requester at each hop (29 T0, 24 T1, 18 T2, 30 interleaved). D: 9/9 T0 carried `may_act` = `{sub: <agent-a service-account uid>, client_id: agent-a}`; 9/9 T1 carried `act` with the same two keys and **0/9 carried `sid`**; actor tokens 12/12 no `sid`. All 131 of 131 token signatures verified against the realm JWKS. | **Supported.** |
| H3 attribution without a token pointer | 1 of 3 per rep, 5 of 15 pooled | **5 of 15**, exactly 1 per rep; events were matched to hops through `token_id` (not order), so this is the events' limit, not the matcher's. No event field links a hop 2 to its hop 1; a scope-equality heuristic would have attributed 15 of 15 here because each planted chain had a distinct scope set, a property of this fixture rather than of the events (recomputed from the raw events at verification: 15 of 15, no ties; not computed in `score.py`). | **Supported.** |
| H4 per-hop scope, R7 detectability | (a) `scope` in exchange events; (b) chain-aware flags `reacquire` 5/5, `new` 5/5, baseline 0/5; root-only flags `new` 5/5, `reacquire` 0/5; (c) `data:admin` label granted without the role | (a) `scope` present on 72/72 exchange and 29/29 login events, 9/9 and 9/9 in D. (b) chain-aware: `reacquire` **5/5**, baseline 0/5, `new` **0/5**; root-only: `reacquire` **0/5**, `new` 0/5, baseline 0/5. (c) **`data:admin` was dropped** from the issued token in 5/5 (S) and 3/3 (D); the event `scope` shows the effective scope (`data:read`), and the requested scope appears in no field (0 of 8 silently reduced hops). Arm D `reacquire`: chain-aware 3/3, root-only 0/3, with the parent link right 9/9 by `userId` + `subject_token_client_id` + nearest time. | (a), (b)-`reacquire` **supported**; (c) **wrong**, and so (b)-`new` is unmeasurable: the plant never became a token and left no trace. |
| H5 enforcer control | `reacquire`/`new` hop 2 → 400 + `TOKEN_EXCHANGE_ERROR` naming the requested scope; baseline 200 | 6 of 6 refusals (3 reps × 2) → 400, `error=invalid_scope`, `client_policy_error_detail` = e.g. `Scopes [data:write] not present in the initial access token [data:read]`; baseline 9/9 hops 200. The error event carries **no `userId`, `sessionId`, `username`, `subject_token_client_id`, `audience` or `scope`** (REST; its only details are `reason`, `auth_method`, `client_auth_method`, `client_policy_error`, `client_policy_error_detail`, `grant_type`), and the log line prints `userId="null"`. The arm D refusals, by contrast, carry `userId`, `username` and `subject_token_client_id`. Statuses were seen in the smoke test; the event contents were not. | **Supported**, with the attribution gap as the finding. |
| H6 arm D depth and scope | hop 2 refused both ways; `two-actors` refused; delegated `reacquire` granted | standard re-exchange of the `act` token: 3/3 → 400 `invalid_request` ("Subject token with a delegation claim is not allowed for standard token exchange"); delegated re-exchange by agent-b: 3/3 → 400 `invalid_token` ("Invalid may_act claim in the subject_token"); `two-actors`: 3/3 → `invalid_scope` at the authorization request, logged as `LOGIN_ERROR` with the full scope string in `reason`. Delegated `reacquire`: 3/3 → 200 with `scope = data:write data:read` and `realm_access.roles` = both, although T0 held only `data:read`. Statuses seen in smoke; claims and events not. | **Supported.** Max explicit chain depth is one actor hop; upscoping is allowed in delegation mode too. |
| H7 log parity | log line carries every REST detail key | On the bench realm: REST-only key is `id` (the event uuid); log-only keys are `authSessionParentId`, `authSessionTabId` (plus `realmName`); error lines print `userId="null"` where REST omits the field. 111 log event lines vs 107 REST events in S (4 are `master`-realm `admin-cli` logins), 50 vs 48 in D (2 the same). | **Supported**; the log is a superset. |
| H8 OCSF fill | events-only fills ≤ `issuer_uid`, `scopes`, `audience`, `created_time` (+`uid` iff token id logged); `parent_uid` 0 hops; records validate clean | see table below; `parent_uid` fillable from events in **0 of 81** exchange events in either arm. 1.9.0 validation of release-shaped records: clean except `attribute_required_missing@user` on the refusal shapes (1 of 3 S shapes, 1 of 6 D shapes); admin records clean (7 and 8 shapes). Main-shaped records at 1.10.0-dev: same single error. | **Supported** on the counts after the amendment-1 correction (the pre-registered list mixed main with 1.9.0); the validator finding is the refusal event, not the mapping. |

## Field inventory

Arm S (default features), REST `/events`, 107 events over 5 reps + 3 enforcer reps; the same per rep (event-set
signature identical across reps for every scenario, 1 distinct of 5 or 3):

| type | n | top-level (non-null) | detail keys |
|---|---|---|---|
| `LOGIN` (ROPC) | 29 | clientId, id, ipAddress, realmId, sessionId, time, type, userId | auth_method, client_auth_method, grant_type, refresh_token_id, refresh_token_provider_id, refresh_token_type, **scope**, **token_id**, username |
| `TOKEN_EXCHANGE` | 72 | clientId, id, ipAddress, realmId, **sessionId**, time, type, userId | **audience**, auth_method, client_auth_method, grant_type, requested_token_type, **scope**, **subject_token_client_id**, **token_id**, username |
| `TOKEN_EXCHANGE_ERROR` (enforcer) | 6 | clientId, error, id, ipAddress, realmId, time, type | auth_method, client_auth_method, client_policy_error, **client_policy_error_detail**, grant_type, reason |

Arm D (preview delegation), 48 events over 3 reps, identical signature per scenario across reps:

| type | n | top-level (non-null) | detail keys |
|---|---|---|---|
| `LOGIN` (code flow + consent) | 9 | clientId, id, ipAddress, realmId, sessionId, time, type, userId | auth_method, code_id, **consent** (value `consent_granted` only; the delegate is not named), redirect_uri, remember_me, response_mode, response_type, username (no scope, no token) |
| `CODE_TO_TOKEN` | 9 | …, sessionId, userId | client_auth_method, code_id, grant_type, refresh_token_*, **scope**, **token_id** |
| `CLIENT_LOGIN` (actor tokens) | 12 | clientId, id, ipAddress, realmId, time, type, userId | client_auth_method, grant_type, token_id, username |
| `TOKEN_EXCHANGE` (delegated) | 9 | clientId, id, ipAddress, realmId, time, type, userId — **no sessionId** | **actor, actor_id, actor_type**, audience, auth_method, client_auth_method, grant_type, requested_token_type, scope, subject_token_client_id, token_id, username |
| `TOKEN_EXCHANGE_ERROR` | 6 | …, userId, error | actor*, auth_method, client_auth_method, grant_type, reason, requested_token_type, subject_token_client_id, username |
| `LOGIN_ERROR` (`two-actors`) | 3 | clientId, error, id, ipAddress, realmId, time, type | reason (full scope string), redirect_uri, response_mode, response_type |

Admin events: realm setup produced 21 (S) and 23 (D) `CREATE` events (CLIENT 4, CLIENT_SCOPE 6, PROTOCOL_MAPPER 3,
REALM_ROLE 3, REALM_ROLE_MAPPING 1, REALM_SCOPE_MAPPING 3, USER 1; D adds AUTHORIZATION_POLICY 2 for the FGAP
delegate permission), each with `authDetails` (admin realm, client, user, ip), `resourcePath` and a JSON
`representation`; the `USER` create representation carries neither the password nor a `credentials` key, and no client secret appears anywhere in the admin events (checked against the fixture values). The four `PUT /client-policies/{profiles,policies}` calls that switched the downscope enforcer on
and off produced **zero** admin events in `/admin-events` and zero lines in the log; the server's admin-event
`resourceType` enum (`results/raw/serverinfo-enums.json`, 40 values) has `REALM`, `CLIENT`, `CLIENT_SCOPE`,
`AUTHORIZATION_POLICY` and others but no client-policy type, so there is no event kind for this change.

## Claims per token position (signature-verified)

| arm | position | n | `sid` | `azp` | `aud` | `scope` | `realm_access` | `act` | `may_act` |
|---|---|---|---|---|---|---|---|---|---|
| S | T0 login | 29 | 29 | app-frontend | agent-a | yes | yes | 0 | 0 |
| S | T1 agent-a | 24 (+15 interleaved) | all | agent-a | agent-b | yes | yes | 0 | 0 |
| S | T2 agent-b | 18 (+15) | all | agent-b | tool-api | yes | yes | 0 | 0 |
| D | T0 login | 9 | 9 | app-frontend | agent-a | incl. `delegation:client:agent-a` | yes | 0 | 9 |
| D | actor tokens | 12 | 0 | agent-a / agent-b | next hop | empty | no | 0 | 0 |
| D | T1 delegated | 9 | **0** | agent-a | agent-b | yes | yes | **9** | 0 |

`may_act` and `act` both carried exactly `{sub: <service-account uid>, client_id: agent-a}`; `act` is not nested
(one level), consistent with one actor hop being the maximum.

## R7 detectability from IdP events alone

Chain-aware check: hop-N data scopes ⊄ hop-(N-1) data scopes, hops linked by `sessionId` (S) or by
`userId` + `subject_token_client_id` + nearest earlier time (D). Root-only check: hop scopes ⊄ alice's
role-derived authority `{data:read, data:write}`.

| arm | scenario | n | per-hop scopes seen in events | chain-aware | root-only |
|---|---|---|---|---|---|
| S | baseline | 5 | [read write] → [read] → [read] | 0 | 0 |
| S | reacquire | 5 | [read write] → [read] → [read write] | **5** | **0** |
| S | new | 5 | [read write] → [read] → [read] (admin dropped) | 0 | 0 |
| D | baseline | 3 | [read write] → [read] | 0 | 0 |
| D | reacquire | 3 | [read] → [read write] | **3** | 0 |
| D | new | 3 | [read write] → [read] (admin dropped) | 0 | 0 |

The `reacquire` row is the R7 result restated on real IdP fields: inside root authority, invisible to a root-only
check, visible to a chain-aware one, and only because Keycloak logs the effective scope per hop. The `new` row is
the surprise: Keycloak filtered `data:admin` out because the client scope's role mapping granted alice nothing, and
neither the token nor the event shows that it was requested (0 of 8 reduced hops recorded the asked-for scope
anywhere). A detection built on IdP events sees a clean `data:read` token. These detection counts come from single-chain sessions; when several chains share one session, the chain-aware check inherits the H3 linkage problem, because the hops can only be grouped by `sessionId` and time, and that case was not scored for detection.

## OCSF 1.9.0 mapping

Classes: `LOGIN`, `CODE_TO_TOKEN`, `CLIENT_LOGIN`, `TOKEN_EXCHANGE` and the error types → `authentication` (3002;
`auth_protocol_id` 6 OAUTH 2.0; exchange hops as activity 4 "Service Ticket Request", a Kerberos caption reused and
noted in `unmapped`, the alternative being 99); the requesting client is `actor.app_name`, alice is `user`, the
audience is `service.name`, the issued token is `authentication_token` (`type_id` 6 Client Token) and the
`delegation` object (`uid` = `token_id`). Admin events: `USER` create and `REALM_ROLE_MAPPING` → `account_change`
(3001, Create / Attach Policy); clients, scopes, mappers and authorization policies → `entity_management` (3004).
`delegation` reaches these classes in 1.9.0 only through the `ai_operation` profile; the records declare it.
`dst_endpoint` is filled from producer configuration (the IdP token endpoint) to satisfy
`at_least_one[service, dst_endpoint]`, and labelled so.

Fill of the `delegation` object per exchange event (S 72, D 9; CODE_TO_TOKEN/LOGIN-with-token likewise):

| attribute | in 1.9.0 | events-only producer | token-in-hand producer (agent's own record) |
|---|---|---|---|
| `uid` | yes | 72/72, 9/9 (`token_id`) | same |
| `parent_uid` | yes | **0/72, 0/9** | 72/72, 9/9 (from the agent's record of the subject token it presented; the IdP never emits it) |
| `issuer_uid` | yes | 72/72, 9/9 (realm issuer) | same |
| `created_time` | yes | 72/72, 9/9 | same |
| `scopes` | main only | 72/72, 9/9 | same |
| `audience` | main only | 72/72, 9/9 | same |
| `expiration_time` | main only | 0 | 72/72, 9/9 (`exp`) |

Validation (`schema.ocsf.io`, version selected by path): release-shaped records at 1.9.0 with `profiles=ai_operation`
pass except `attribute_required_missing@user` on the `TOKEN_EXCHANGE_ERROR` (S) and `LOGIN_ERROR` (D) shapes, which
is the IdP omission, not a mapping choice; main-shaped records at 1.10.0-dev show the same single error; all admin
records pass. Records in `results/ocsf_records_*.jsonl`, verdicts in `results/ocsf_mapping.json`.

## Timing (under contention; not a finding)

Token-endpoint round trips, monotonic, median ms (CV) over successful hops: S login 75.8 (0.31, n=29), S exchange
19.0 to 21.2 (0.17 to 0.47, n=15 to 24); D code-to-token 24.0 (0.49, n=9), D delegated exchange 25.1 (0.33, n=9),
actor client-credentials 17.5 (0.43, n=9). The whole run, both container starts included, took 1 min 59 s.

## Held constant and varied

Held constant: image digest, realm layout built by the same REST calls, user and roles, the three scope plants, the
event configuration, the capture method, one host, one harness. Varied: server feature set (arm), login grant
(ROPC vs code+consent, forced by the consent requirement of the delegation scope), enforcer on/off (S only), the
seeded interleaving order per rep. Repetition changed nothing that was scored: every scenario's event-set signature
was identical across reps, and every hop's status was identical across reps.

## Limits

- One IdP, one version, dev mode, H2 database, HTTP on localhost. Another IdP's exchange event may well carry the
  subject token id; this measures Keycloak 26.8.1 and nothing wider.
- Arm D's parent link (`userId` + `subject_token_client_id` + nearest time) was right 9 of 9 in sequential
  single-chain runs; an interleaved arm D scenario was not pre-registered and not run, so the attribution figure for
  the delegation feature under concurrency is not measured.
- The `new` class was tested with a realm-role-backed client scope. A client scope with no role mapping might be
  granted as a bare label; that variant was not run.
- No `aud` check at the resource server, no introspection events, no refresh-token exchange, no offline sessions.
- The enforcer was applied with the `any-client` condition; a narrower policy might log differently.
- Admin-event coverage of the client-policy change was measured on REST and the log at `success=info`; the
  possibility that a DEBUG-level log line exists was not checked.
- Timings are under a load average of 18 to 19 and a 4-core cap; they show only that nothing was slow enough to
  matter.
- The runtime fixture secrets (alice's password, four client secrets) were redacted from
  `results/raw/*/fixture-secrets.json` and `results/raw/*/realm-config.json` after the run; the realms were deleted
  with their containers, and nothing in `score.py` or `map_ocsf.py` reads those two files.

## Deviations from the pre-registration

Recorded as amendment 1 in `PREREGISTRATION.md`: the H8 attribute list was read from OCSF main rather than 1.9.0
(fill is reported against both); arm D hops were linked without `sessionId` by a rule chosen after seeing the event
shape; log parity was computed on the bench realm only; `dst_endpoint` is producer configuration. No harness line
changed after the freeze and nothing was re-run. Statuses for H5 and H6 had been seen in the smoke test and are
labelled so in the table.

## Commands

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run_all.sh                                   # both arms, ~2 min; results/raw/driver.log
.venv/bin/python score.py                      # results/score.json, results/tables.md
.venv/bin/python map_ocsf.py                   # results/ocsf_mapping.json, results/ocsf_records_*.jsonl
```
