| cell | outcome | hook fires | hook decisions (tool, decision, agent?, mcp source) | permission_denials | sys permission_denied | turns | cost USD |
|---|---|---|---|---|---|---|---|
| A1 | BLOCKED by permission rule / flow | 0 | - | 1 | 1 | 2 | 0.0019975 |
| A2 | BLOCKED by permission rule / flow | 1 | Bash:none | 1 | 1 | 2 | 0.0027470899999999998 |
| B1 | BLOCKED by hook (reason reached model) | 1 | Bash:deny | 1 | 0 | 2 | 0.0025644 |
| B2 | BLOCKED by hook (reason reached model) | 1 | Bash:deny | 1 | 0 | 2 | 0.00261252 |
| B3 | BLOCKED by hook (reason reached model) | 1 | Bash:deny | 1 | 0 | 2 | 0.00063664 |
| B4 | BLOCKED by hook (reason reached model) | 1 | Bash:deny | 1 | 0 | 2 | 0.0006119300000000001 |
| B5 | BLOCKED by hook (reason reached model) | 1 | Read:deny | 1 | 0 | 2 | 0.0025412900000000003 |
| B6 | BLOCKED by hook (reason reached model) | 1 | Read:deny | 1 | 0 | 2 | 0.0025995099999999998 |
| C1 | BLOCKED by permission rule / flow | 0 | - | 1 | 1 | 2 | 0.0006259 |
| C2 | BLOCKED by permission rule / flow | 0 | - | 1 | 1 | 2 | 0.00064714 |
| C3 | BLOCKED by permission rule / flow | 0 | - | 1 | 1 | 2 | 0.00058703 |
| C4 | BLOCKED by permission rule / flow | 0 | - | 1 | 1 | 2 | 0.0006511 |
| C5 | BLOCKED by permission rule / flow | 0 | - | 1 | 0 | 2 | 0.00064412 |
| D1 | RAN (marker created) | 0 | - | 0 | 0 | 2 | 0.0023715200000000002 |
| D2 | BLOCKED by permission rule / flow | 0 | - | 1 | 1 | 2 | 0.00275216 |
| D2b | RAN (marker created) | 0 | - | 0 | 0 | 2 | 0.00058042 |
| D3 | RAN (marker created) | 0 | - | 0 | 0 | 2 | 0.00058042 |
| D4 | RAN (marker created) | 0 | - | 0 | 0 | 2 | 0.00058038 |
| E1 | RAN (marker created) | 0 | - | 0 | 0 | 2 | 0.0005673399999999999 |
| E1b | RAN (marker created) | 0 | - | 0 | 0 | 2 | 0.0005680399999999999 |
| E1c | RAN (marker created) | 0 | - | 0 | 0 | 2 | 0.00054264 |
| E2 | RAN (marker created) | 0 | - | 0 | 0 | 2 | 0.00054264 |
| E2b | BLOCKED by hook (reason reached model) | 1 | Bash:deny | 1 | 0 | 2 | 0.00065964 |
| E3 | BLOCKED by permission rule / flow | 0 | - | 1 | 1 | 2 | 0.0006015300000000001 |
| E4 | BLOCKED by permission rule / flow | 0 | - | 1 | 1 | 2 | 0.00059403 |
| E5 | BLOCKED by hook (reason reached model) | 1 | Bash:deny | 1 | 0 | 2 | 0.00067514 |
| E6 | BLOCKED by permission rule / flow | 1 | Bash:allow | 1 | 0 | 2 | 0.0005885300000000001 |
| E7 | BLOCKED by permission rule / flow | 0 | - | 1 | 1 | 2 | 0.00061249 |
| F1 | OTHER | 2 | Agent:none; Bash:none agent | 0 | 0 | 2 | 0.0052949450000000006 |
| F2 | BLOCKED by hook (reason reached model) | 2 | Agent:none; Bash:deny agent | 1 | 0 | 2 | 0.0028100950000000003 |
| G1 | OTHER | 1 | mcp__t9fixture__echo:none mcp:dynamic | 0 | 0 | 3 | 0.00281343 |
| G2 | BLOCKED by hook (reason reached model) | 1 | mcp__t9fixture__echo:deny mcp:dynamic | 1 | 0 | 3 | 0.0009214000000000002 |
| G3 | OTHER | 0 | - | 0 | 0 | 4 | 0.00383001 |
| H1 | BLOCKED by hook (reason reached model) | 1 | Bash:deny | 1 | 0 | 2 | 0.0006651000000000001 |
| H1b | BLOCKED by hook (reason reached model) | 1 | Bash:deny | 1 | 0 | 2 | 0.00062944 |
| H2 | BLOCKED by permission rule / flow | 0 | - | 1 | 1 | 2 | 0.0006251 |
| H2b | BLOCKED by permission rule / flow | 0 | - | 1 | 1 | 2 | 0.0006144900000000001 |
