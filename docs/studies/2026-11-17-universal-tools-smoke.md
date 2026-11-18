# Universal tool integration smoke observations

November 17, 2026. Gateway uacp-tools-v1; shared dependency revision 1a17b9f2ec8c72f3b99fd615c89b4ba9ebcd6191. [Machine-readable synthetic results](2026-11-17-universal-tools-smoke.json).

This is a small integration check, not a repeated baseline study or a new claim about general model reliability. Native calling used real tool schemas and actual assistant tool-call / tool-result messages. There was no paid tool request or provider fallback. LM Studio's loaded state was read once; no model was switched, loaded or unloaded.

| Route/model | Outcome | Tool evidence | Interpretation |
|---|---|---|---|
| LM Studio qwen3.5-9b-uncensored-hauhaucs-aggressive@q6_k | 30-second inference timeout | Zero tool calls | Request did not reach the gateway; eventual model correctness/tool capability is unmeasured under this budget. |
| Groq qwen/qwen3.8-27b | Completed within three model turns | Two successful real scientific_calculator calls; distance/duration yielded 60 km/h; second call evaluated 120 km | Final answer correctly reported 60 km/h. The second call was unnecessary for this problem, so successful execution does not imply efficient planning. |

Both cases used maximum 3 agent iterations. The local case allowed 1,024 output tokens per request; Groq allowed 768. Temperature was zero. Groq used the existing configured account; no new provider/key or paid search/extraction was used. The scientific engine reported qalc 5.13.0 at 50 significant digits in the Groq run. SDK automatic retries were disabled for native model requests.

Separate application evidence: 511 host tests, including real Qalculate checks, passed; 57 shared control-plane tests passed, including MCP and architecture maps; ten DOM scripts passed. The live dashboard exposed eight local tools plus three read-only UACP tools through a persistent local MCP connection. Direct live checks covered calculator/scientific units, file write/read, loopback fetch, datetime(now), invalid-type rejection, UACP registry validation and checksum-matched replay. Search/extraction behavior was covered with offline/frozen tests and readiness checks, not a paid live request.

The original 1,200-case study and baseline-v1 scorers are unchanged. A new matched repeated study is needed to estimate improvement, especially for the earlier GPT-OSS native-protocol failure and final-answer propagation issues. See [universal tools](../universal-tools.md), [issues/resolutions](../issues-and-resolutions.md) and [creator acknowledgements](../credits-and-sources.md).

Subsequent final regression validation passed 517 application tests and 58 control-plane tests after adding actionable validation diagnostics, exact basic decimal arithmetic and structured MCP scalar/null preservation. The smoke observations above retain the revision and test counts at collection time; the final Playpen dependency pins control-plane revision c770b262154c32d7e1d6056f1fe15d1159c9a6de.
