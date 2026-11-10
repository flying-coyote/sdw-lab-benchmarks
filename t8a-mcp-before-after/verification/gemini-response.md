**CLAIM 1: AGREE**  
The raw capture recounts confirm every single metric change (connections, headers, methods, and `_meta` fields) between B and C. Because both arms run SDK 2.3.0 and differ only in the negotiated revision, these differences are strictly protocol-revision facts.

**CLAIM 2: OVERCLAIM**  
Arm B produces 12 server spans, not 11, and its 12th span (`notifications/initialized`) lacks a client parent. Therefore, the claim that SDK 2.3.0 uniformly introduces 11 client-parented server spans regardless of revision overstates what Arm B actually produced.

**CLAIM 3: AGREE**  
The excerpt and source citation confirm that 1.30.0 unconditionally maps unhandled exceptions to `code=0` (preventing `-32002`), B and C return `-32602`, and HTTP 400 only appears in C.

**CLAIM 4: AGREE**  
Code excerpts show `ClientSession.initialize()` restricts handshake negotiation to `LATEST_HANDSHAKE_VERSION` (2025-11-25), whereas `mcp.Client(mode="auto")` probes `server/discover` and successfully negotiated 2026-07-28 across all runs with default settings.

**CLAIM 5: DISAGREE**  
H5 was marked "supported" despite triggering two explicit pre-registered falsification conditions: B differed from C in server span count (12 vs. 11), and B's extra server span was not a child of a client span.
