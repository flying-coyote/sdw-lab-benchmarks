---
type: benchmark-prereg
title: "T7: does an identity provider's audit trail record an agent delegation chain? (pre-registration)"
created: 2026-11-09
review_ref: project1/02-projects/securitydataworks/SITE-REVIEW-2026-11-09.md, AI-research bench T7 (follows R7 delegation-chain-query)
status: frozen by agent before run; not owner-reviewed
---

# T7 pre-registration: IdP delegation logging across an OAuth 2.0 token-exchange chain

## Question

R7 (`delegation-chain-query/`) measured the cost of detecting scope escalation when every delegation hop is
already a record, and found that a root-only check misses the `reacquire` class (a hop re-grants authority an
earlier hop had dropped, while staying inside the human root's authority). This bench asks the upstream question:
when the hops are real OAuth 2.0 Token Exchange (RFC 8693) operations at an identity provider, does the IdP's own
audit trail record the chain at all? Specifically, for a chain `user -> app-frontend -> agent A -> agent B ->
tool API` run against Keycloak 26.8.1:

1. Which fields does each hop's audit event carry, on the admin REST events API and on the stdout log line a SIEM
   would ingest?
2. Does any event carry a *parent pointer* (an identifier of the subject token that was exchanged, or the client
   it was issued to), so that the chain can be reconstructed from IdP events alone, rather than inferred from
   session id and time order?
3. Do the issued access tokens carry the RFC 8693 `act` / `may_act` claims, and under which server feature set?
4. Is the R7 `reacquire` escalation detectable from IdP events alone, and does a root-only check over those same
   events miss it, as it did over R7's synthetic records?
5. How far do the fields map onto OCSF 1.9.0 (`authentication` 3002, `account_change` 3001, and the `delegation`
   object), and how many of the `delegation` object's attributes can an IdP-only producer fill per hop?

## System under test and arms

Keycloak 26.8.1, image `quay.io/keycloak/keycloak@sha256:3f3c5f8e03c614774b4bd9173b88391fefa4153bfc010d8012d59ad825377332`
(tag 26.8.1, published 2026-10-31; 26.8.2 appeared on 2026-11-09 and was not used), `start-dev` with the dev-file
H2 database, bound to `127.0.0.1:8080` only, `--cpus=4 --memory=2g`, JVM `-XX:ActiveProcessorCount=4`. Two arms,
run one after the other in separate containers because they differ in server feature flags:

- **Arm S (default features).** Standard Token Exchange V2 (`TOKEN_EXCHANGE_STANDARD_V2`, a default feature in
  26.8.1), enabled per requester client with the client attribute `standard.token.exchange.enabled=true`. No
  `actor_token`. This is the configuration a deployment gets without opting into previews.
- **Arm D (preview features).** `KC_FEATURES=token-exchange-delegation,parameterized-scopes`, which Keycloak's
  securing-apps guide documents as its RFC 8693 delegation support: the user consents to a parameterized scope
  `delegation:client:<actor>` and the issued token carries `may_act`; the actor then exchanges with `subject_token`
  plus its own `actor_token` and receives a token carrying `act`. Both features are marked PREVIEW in
  `/admin/serverinfo`. The guide also states the delegated token "is issued in a transient session, so no refresh
  token is returned and the token carries no session identifier"; whether that costs the audit trail its session
  linkage is one of the things measured.

Both arms share one realm layout, built through the admin REST API (not `--import-realm`, so that the setup
itself produces admin events): realm roles `data-read`, `data-write`, `data-admin`; user `alice` holding
`data-read` and `data-write` only (her root authority); client scopes `data:read`, `data:write`, `data:admin`, each
mapping exactly one realm role; audience scopes `aud:agent-a`, `aud:agent-b`, `aud:tool-api` carrying an Audience
mapper (Keycloak's exchange requires the requester to be in the subject token's `aud`, and the `audience=`
parameter only filters audiences, never adds them); confidential clients `app-frontend` (ROPC in arm S;
authorization code with consent in arm D), `agent-a`, `agent-b` (exchange enabled; service accounts enabled for
the arm D actor tokens), `tool-api` (audience target only). Every client has `fullScopeAllowed=false`, so role
claims are filtered by the effective scopes. Events: `eventsEnabled`, all event types, `adminEventsEnabled` with
details, `jboss-logging` listener at `success=info` / `error=warn`. Passwords, client secrets and the bootstrap
admin password are generated at run time and written only under `results/raw/<arm>/fixture-secrets.json`, labelled
as test fixtures. Arm D additionally enables FGAP V2 (`adminPermissionsEnabled`) and grants the `delegate` scope on
Users to a client policy naming `agent-a` and `agent-b` (UNANIMOUS strategy, the only one the server accepts).

## Scenarios (fixed; the hop scopes are the plants)

Arm S, each scenario a fresh ROPC login of alice at `app-frontend` with scope `data:read data:write`, then
agent-a exchanges for `audience=agent-b`, then agent-b exchanges for `audience=tool-api`:

| scenario | hop 1 (agent-a) scope | hop 2 (agent-b) scope | class (R7 vocabulary) |
|---|---|---|---|
| `baseline` | `data:read` | `data:read` | attenuating chain, no escalation |
| `reacquire` | `data:read` | `data:read data:write` | write dropped at hop 1, re-granted at hop 2; inside root authority |
| `new` | `data:read` | `data:read data:admin` | admin never held by alice (R7's bit 15) |
| `interleaved` | one login; three agent-a exchanges (`data:read` / `data:read data:write` / `data:write`) | three agent-b exchanges in a seeded shuffled order (`data:read` / `data:read data:write` / `data:write`) | attribution test: which hop 2 came from which hop 1 |

Then the control condition: a realm client policy applying the `downscope-assertion-grant-enforcer` executor to
every client (condition `any-client`), and `baseline`, `reacquire`, `new` run again (the interleaved scenario is
not run under the enforcer). The policy is removed afterwards.

Arm D, each scenario a scripted authorization-code login with consent at `app-frontend`:

| scenario | login scope (T0) | agent-a delegated exchange (`actor_token` = agent-a client-credentials token) |
|---|---|---|
| `baseline` | `openid data:read data:write delegation:client:agent-a` | `audience=agent-b scope=data:read`; then agent-b attempts hop 2 on the delegated token twice: standard exchange, and delegated exchange with agent-b's own actor token |
| `reacquire` | `openid data:read delegation:client:agent-a` | `scope=data:read data:write` (write absent from T0) |
| `new` | `openid data:read data:write delegation:client:agent-a` | `scope=data:read data:admin` |
| `two-actors` | `openid data:read delegation:client:agent-a delegation:client:agent-b` | login only: can one subject token pre-authorize two actors? |

## Repeats

Arm S: 5 repetitions of the four scenarios, then 3 repetitions of the three enforcer scenarios, all in one
realm and one container. Arm D: 3 repetitions of the four scenarios. Outcomes that can vary are HTTP status per
hop, the event set per scenario (compared modulo identifiers and timestamps), and the token-endpoint round-trip
time (monotonic `time.perf_counter_ns`), reported as median and CV per hop type. The run shares the host with
other benches and is capped to 4 cores under `nice -n 10`, so the latencies are reported as taken under
contention and are not a finding.

## Hypotheses, and what would prove each wrong

- **H1 (no parent pointer).** No `TOKEN_EXCHANGE` event, on REST or in the log line, carries an identifier of the
  subject token (its `jti`) or names the client the subject token was issued to (its `azp`). Tested by searching
  every event detail value against the captured subject-token `jti` and `azp` of the hop it records. Wrong if any
  detail matches. Prediction: absent in both arms.
- **H2 (claims).** Arm S tokens carry neither `act` nor `may_act`; `sub` stays alice, `azp` becomes the requester
  client at each hop. Arm D: T0 carries `may_act` with `sub` = agent-a's service-account user id and
  `client_id=agent-a`; the delegated T1 carries `act` with `client_id=agent-a` and carries no `sid`. Wrong if
  `act` appears in arm S, is missing in arm D, or arm D's T1 carries a session identifier.
- **H3 (reconstruction without a pointer).** In the arm S `interleaved` scenario, the rule "attribute each
  agent-b `TOKEN_EXCHANGE` event to the nearest earlier agent-a `TOKEN_EXCHANGE` event in the same `sessionId`"
  attributes 1 of 3 hop-2 events correctly per repetition (the shuffled order makes the nearest predecessor the
  last agent-a hop for all three), pooled 5 of 15. Wrong if accuracy is 15 of 15, which would mean the events
  carry something that disambiguates (then H1 is also wrong), or if `sessionId` is absent so that no attribution
  is possible at all.
- **H4 (per-hop scope and R7 detectability).** (a) The `TOKEN_EXCHANGE` event details include the issued token's
  `scope`. (b) A chain-aware check over events alone (hop-N scope not a subset of hop-(N-1) scope, hops linked by
  sessionId and client adjacency in the single-chain scenarios) flags `reacquire` 5 of 5 and `new` 5 of 5 and
  `baseline` 0 of 5; a root-only check (hop scope not a subset of alice's role-derived authority
  `{data:read, data:write}`) flags `new` 5 of 5 and `reacquire` 0 of 5. (c) Keycloak grants the `data:admin` scope
  label in `new` even though alice lacks the role, so `new` is visible in the `scope` claim and detail while
  `realm_access.roles` lacks `data-admin`. Wrong if (a) fails (then nothing about scope is detectable from IdP
  events), if root-only flags `reacquire`, or if the `new` hop is refused or issued without the label.
- **H5 (enforcer control).** With `downscope-assertion-grant-enforcer`, `reacquire` and `new` hop 2 return 400 and
  produce a `TOKEN_EXCHANGE_ERROR` event whose details name the requested `scope`; `baseline` stays 200. Wrong if
  the error event lacks the requested scope (the IdP would log a refusal but not what was attempted) or if
  `baseline` is refused.
- **H6 (arm D depth and scope).** The delegated token cannot be re-delegated: both agent-b hop-2 attempts are
  refused (one chain of depth 1 actor is the maximum), and `two-actors` is refused at the authorization request.
  The `reacquire` delegated exchange succeeds and the token's `scope` contains `data:write` although T0 did not,
  because the guide says the delegated token's scopes come from the actor client's configuration. Wrong if a hop-2
  attempt succeeds, or the delegated `reacquire` is refused.
- **H7 (log line parity).** Every detail key present on a REST `TOKEN_EXCHANGE` event is also present in the
  corresponding `jboss-logging` line. Wrong if any key is dropped or its value masked.
- **H8 (OCSF fill).** Of the seven `delegation` attributes (`uid`, `parent_uid`, `issuer_uid`, `scopes`,
  `audience`, `created_time`, `expiration_time`), an IdP-events-only producer fills at most `issuer_uid`, `scopes`,
  `audience`, `created_time`, plus `uid` only if the event names the issued token id; `parent_uid` is fillable in
  0 hops in either arm from events alone. Records mapped to `authentication` (3002) with the `delegation` object
  pass `schema.ocsf.io/api/v2/validate` with zero errors. Wrong if `parent_uid` is fillable from events alone in
  any hop, or if the validator reports errors on a record built only from fields present.

## Scoring rubric (fixed before the run)

- **Chain linkage grade** per arm: EXPLICIT (an event field identifies the subject token or its client),
  IMPLICIT (hops share a `sessionId` and are ordered in time, nothing more), NONE (no shared identifier).
- **Field inventory**: for each event type seen (`LOGIN`, `CODE_TO_TOKEN`, `CLIENT_LOGIN`, `TOKEN_EXCHANGE`,
  `TOKEN_EXCHANGE_ERROR`, and admin event operation types), the set of top-level fields and detail keys, counted
  across repetitions; REST and log line side by side.
- **Claims inventory** per token position (T0, T1, T2, actor tokens): presence of `jti`, `sid`, `azp`, `aud`,
  `scope`, `realm_access.roles`, `act`, `may_act`, and whether the signature verified against the realm JWKS.
- **Detection matrix** (H4): per scenario and repetition, flagged or not under chain-aware and root-only checks.
- **Attribution accuracy** (H3): correct out of 15.
- **OCSF fill table** (H8): per hop and arm, each `delegation` attribute marked filled-from-events /
  filled-only-with-token-in-hand / not fillable, plus the validator verdict counts.

## Pre-run instrument development (declared)

Before freezing, the harness was smoke-tested against two throwaway realms (`t7s-smoke`, `t7d-smoke`) in a dev
container, to the level of HTTP status codes per hop and the server's `error_description` strings on refused
hops. What was seen and is therefore not a blind prediction: all arm S hops returned 200 without the enforcer;
with the enforcer, `reacquire` and `new` hop 2 returned 400 and `baseline` 200; in arm D the consent login,
actor token and delegated exchange returned 200, both agent-b hop-2 attempts returned 400 (standard exchange:
"Subject token with a delegation claim is not allowed for standard token exchange"; delegated: "Invalid may_act
claim in the subject_token"), and `two-actors` was refused at the authorization request with `invalid_scope`.
Those parts of H5 and H6 are confirmations of a smoke result, and are labelled so in RESULTS. No token claim, event
or admin event was inspected before the freeze, and the smoke outputs were deleted. Three harness fixes came out of
the smoke: FGAP V2 accepts only the UNANIMOUS strategy (one client policy naming both actors); the delegation
client scopes had to be added to `app-frontend`'s optional scopes explicitly; and `http.cookiejar` withheld the
`KC_RESTART` cookie on the login form POST, so the scripted browser flow carries cookies as a plain dict.

## Instrument and environment

- Host: the Beelink (AMD Ryzen 7 5800H), WSL2 kernel 6.6.87.2-microsoft-standard-WSL2, 14 vCPU and 47 GB
  visible; Windows power plan not readable from the guest. Docker 29.5.3 (Docker Desktop, WSL2 backend).
- Clock: chrony; `chronyc tracking` is recorded in `results/raw/driver.log` before and after the run. All
  durations are `time.perf_counter_ns` (monotonic).
- Harness: Python 3.12.3 venv, `PyJWT==2.15.1`, `cryptography==50.0.2` (`requirements.txt`). `kc.py`
  (stdlib HTTP, signature-verified JWT decode, scripted login/consent), `harness.py` (setup, run, enforcer,
  capture), `run_all.sh` (driver). Analysis code (`score.py`, `map_ocsf.py`) is written after the freeze against
  the rubric above and its hashes are recorded in RESULTS.
- Capture surfaces: admin REST `/admin/realms/{realm}/events` and `/admin-events` (paginated, 500 per page),
  `docker logs --since <arm start>` for the `jboss-logging` lines, and the token responses with verified claims
  per hop (`results/raw/<arm>/chains-rep*.json`). Access tokens themselves are not stored; `jti` and claims are.
- Isolation is NOT met (other benches share the host). Load average is recorded before and after each repetition.

## Stop rule and cost

Wall budget 2.5 h from the freeze time. A container that fails its 240 s readiness wait twice marks its arm DNF
and the arm is published as such. A hop that fails outside the predicted refusals is recorded with its status
and `error_description` and the scenario continues where it can. Local CPU and network only (image pull, OCSF
validator calls to `schema.ocsf.io`); no paid API calls; $0.

## Safety and scope

Defensive measurement of audit-trail completeness. The only "attack content" is a scope string requested at a
token endpoint of a localhost-bound dev IdP with runtime-generated fixture credentials. No exploit code, no real
credentials, nothing about any employer.

## Harness hashes at freeze

See `results/freeze.txt` (sha256 of `kc.py`, `harness.py`, `run_all.sh`, `requirements.txt`, and of this file,
with the UTC freeze time). Any later change is a dated amendment below, never an in-place edit.

## Amendments

(none at freeze)

- **2026-11-10, amendment 1 (analysis-side, after the run; no harness line changed, no re-run).** Three
  things the pre-registration got wrong about the instruments, found while scoring, recorded here rather than
  edited in place:
  1. **H8's attribute list mixed OCSF main with the 1.9.0 release.** The seven `delegation` attributes were read
     from a copy of the object on OCSF main (`agent-toolcall-schemas/ref/delegation_main.json`). The 1.9.0 release
     object has four (`uid`, `parent_uid`, `issuer_uid`, `created_time`); `scopes`, `audience` and `expiration_time`
     exist only on main (1.10.0-dev), and in 1.9.0 the `delegation` attribute reaches `authentication` only
     through the `ai_operation` profile. RESULTS reports the fill against both sets and validates a release-shaped
     record at 1.9.0 and a main-shaped record at 1.10.0-dev (version selected by URL path; the validator ignores
     a `version` query parameter, checked with a main-only attribute and a bogus attribute).
  2. **Arm D linkage.** H4's chain-aware check links hops by `sessionId`. Arm D's delegated `TOKEN_EXCHANGE` event
     has no `sessionId` (the token is issued in a transient session, as the guide says), so for arm D the scorer
     links each exchange to the nearest earlier `CODE_TO_TOKEN` of the same `userId` whose `clientId` equals the
     exchange's `subject_token_client_id`, and reports whether that link was right against the agent's own
     record. This was not pre-registered; it is the only link the arm D event offers.
  3. **Log-line parity (H7) is computed on the bench realm only.** The container log carries every realm, including
     the `admin-cli` logins to `master`, so log lines are filtered by `realmName` before comparison.
  Also recorded: `dst_endpoint` in the OCSF records is producer configuration (the IdP's own token endpoint), filled
  to meet the `authentication` class constraint `at_least_one[service, dst_endpoint]`, and labelled so in `unmapped`.
