# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: runtime-dashboard.visual.spec.ts >> runtime-dashboard visual baselines >> DS8 governed run paper >> semantic DOM closes overview and report paper egress
- Location: e2e/runtime-dashboard.visual.spec.ts:1228:5

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByTestId('annotation-surface-panel').getByText('DS8-BROWSER-LOCAL-MUST-NOT-PRINT')
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 5000ms
  - waiting for getByTestId('annotation-surface-panel').getByText('DS8-BROWSER-LOCAL-MUST-NOT-PRINT')

```

# Page snapshot

```yaml
- generic [ref=e2]:
  - generic [ref=e3]:
    - link "Skip to content" [ref=e4] [cursor=pointer]:
      - /url: "#main-content"
    - generic [ref=e6]:
      - complementary "Primary workspace navigation" [ref=e7]:
        - generic [ref=e9]:
          - generic [ref=e10]:
            - img [ref=e11]
            - generic [ref=e16]:
              - paragraph [ref=e17]: PolisyOS Runtime
              - heading "Atlas" [level=1] [ref=e18]
          - paragraph [ref=e19]: Editorial analyst shell for command, evidence, and decision work.
        - navigation "Primary workspace navigation" [ref=e20]:
          - link "Command Center" [ref=e21] [cursor=pointer]:
            - /url: /
          - link "Scenario Composer" [ref=e22] [cursor=pointer]:
            - /url: /compose
          - link "Runs & Decisions" [ref=e23] [cursor=pointer]:
            - /url: /runs
          - link "Evidence Fabric" [ref=e24] [cursor=pointer]:
            - /url: /evidence
          - link "Lex & Knowledge" [ref=e25] [cursor=pointer]:
            - /url: /knowledge
          - link "Platform Health" [ref=e26] [cursor=pointer]:
            - /url: /platform
        - group "Interface mode" [ref=e27]:
          - generic [ref=e28]: Interface mode
          - radiogroup "Interface mode" [ref=e29]:
            - generic [ref=e30] [cursor=pointer]:
              - radio "Clerk" [ref=e31]
              - generic [ref=e33]: Clerk
            - generic [ref=e34] [cursor=pointer]:
              - radio "Analyst" [checked] [ref=e35]
              - generic [ref=e37]: Analyst
        - generic [ref=e38]:
          - paragraph [ref=e39]: Watch status
          - strong [ref=e40]: Unavailable
      - generic [ref=e41]:
        - banner [ref=e42]:
          - generic [ref=e43]:
            - generic [ref=e44]:
              - img [ref=e45]
              - generic [ref=e50]: Atlas analyst shell
            - paragraph [ref=e51]: Run analysis
            - heading "Decision workspace turns artifacts into one operating view" [level=2] [ref=e52]
            - paragraph [ref=e53]: Inspect run lifecycle, decisions, governance, and provenance in one workspace.
          - generic [ref=e54]:
            - generic [ref=e55]: ok
            - generic [ref=e56]: Polling fallback
            - generic [ref=e57]: Checking
            - generic [ref=e58]: "Capability manifest: 20"
            - generic [ref=e59]: Queue stable
            - button "Theme" [ref=e60]:
              - generic [ref=e61]: "Theme: auto"
            - 'button "Trust View mode: Trust expanded. Press to cycle." [pressed] [ref=e62]':
              - img [ref=e63]
              - generic [ref=e66]: Trust expanded
            - button "Locale English" [ref=e67]:
              - generic [ref=e68]: English
            - button "Locale Українська" [ref=e69]:
              - generic [ref=e70]: Українська
            - link "Open runs" [ref=e71] [cursor=pointer]:
              - /url: /runs
              - generic [ref=e72]: Open runs
            - link "Launch scenario" [ref=e73] [cursor=pointer]:
              - /url: /compose
              - generic [ref=e74]: Launch scenario
        - generic [ref=e75]:
          - radiogroup "Counterfactual mode" [ref=e76]:
            - radio "Actual" [checked] [ref=e77]
            - radio "Actual + Scenario" [ref=e78]
            - radio "Scenario" [ref=e79]
          - generic [ref=e80]:
            - generic [ref=e82]: Scenario
            - combobox "Scenario" [ref=e83]:
              - option "Choose scenario" [selected]
              - option "What if the primary policy lever moved within safe bounds? · Computed"
        - main [ref=e84]:
          - generic [ref=e86]:
            - complementary "Ambient telemetry" [ref=e87]:
              - generic [ref=e88]:
                - generic [ref=e89]:
                  - img [ref=e91]
                  - generic [ref=e93]:
                    - paragraph [ref=e94]: Ambient telemetry
                    - paragraph [ref=e95]: R_core_api_001
                - generic [ref=e96]: degraded
              - generic [ref=e97]:
                - generic [ref=e98]:
                  - generic [ref=e99]:
                    - img [ref=e100]
                    - text: Transport
                  - strong [ref=e106]: blocked
                - generic [ref=e107]:
                  - generic [ref=e108]:
                    - img [ref=e109]
                    - text: Temporal scope
                  - strong [ref=e112]: Sep 1, 2026, 9:54 PM
                - generic [ref=e113]:
                  - generic [ref=e114]: Feature flags
                  - strong [ref=e115]: 11 on · env/ready
                - generic [ref=e116]:
                  - generic [ref=e117]: Surface
                  - strong [ref=e118]: overview
                - generic [ref=e119]:
                  - generic [ref=e120]:
                    - generic [ref=e121]:
                      - img [ref=e122]
                      - text: Trust
                    - strong [ref=e123]: 60%
                  - generic "Global trust threshold" [ref=e124]:
                    - slider "Global trust threshold" [ref=e128]
            - generic [ref=e130]:
              - region "Run R_core_api_001" [ref=e132]:
                - navigation "Run lineage" [ref=e133]:
                  - link "Runs" [ref=e134] [cursor=pointer]:
                    - /url: /runs
                  - generic [ref=e135]: /
                  - generic [ref=e136]: R_core_api_001
                  - generic [ref=e137]: /
                  - link "Decision artifact" [ref=e138] [cursor=pointer]:
                    - /url: /artifacts/sha256:9836fd27dedc46ca60fa8a3939d39d8d4e5c99280149a8e16ada1791a7a2bc62
                  - generic [ref=e139]: /
                  - generic [ref=e140]: GOV001
                - paragraph [ref=e141]: Decision artifact
                - heading "reject" [level=2] [ref=e142]
                - button "Run decision score 0.67 ratio, untraced provenance available, Freshness Unknown" [ref=e144]:
                  - generic [ref=e145]: "0.67"
                  - generic [ref=e146]: ratio
                  - img [ref=e147]
                  - img [ref=e150]
                - generic [ref=e153]:
                  - generic [ref=e154]:
                    - text: Evaluator
                    - strong [ref=e155]: REPLAN_DATA
                  - generic [ref=e156]:
                    - text: Governance
                    - strong [ref=e157]:
                      - button "blockers 1 1 blockers, untraced provenance available, Freshness Unknown" [ref=e158]:
                        - generic [ref=e159]: "1"
                        - generic [ref=e160]: blockers
                        - img [ref=e161]
                        - img [ref=e164]
                  - group [ref=e167]:
                    - generic "Diagnostics" [ref=e168] [cursor=pointer]
              - generic [ref=e170]:
                - generic [ref=e171]:
                  - generic [ref=e172]:
                    - generic [ref=e173]:
                      - group "Runs & Decisions" [ref=e174]:
                        - generic [ref=e175]: Runs & Decisions
                        - list [ref=e176]:
                          - listitem [ref=e177]:
                            - img "Policy run" [ref=e178]
                            - generic [ref=e182]: Policy run
                          - listitem [ref=e183]:
                            - img "Governance blocked" [ref=e184]
                            - generic [ref=e188]: Governance blocked
                          - listitem [ref=e189]:
                            - img "Replayable" [ref=e190]
                            - generic [ref=e194]: Replayable
                      - heading "Run R_core_api_001" [level=3] [ref=e195]
                      - paragraph [ref=e196]: Inspect run lifecycle, decisions, governance, and provenance in one workspace.
                    - generic [ref=e197]:
                      - generic [ref=e198]: fail
                      - generic [ref=e199]: Core run
                      - link "evidence" [ref=e200] [cursor=pointer]:
                        - /url: /evidence?focus=overview&runId=R_core_api_001
                        - generic [ref=e201]: evidence
                      - link "Audit report" [ref=e202] [cursor=pointer]:
                        - /url: /runs/R_core_api_001/report
                        - generic [ref=e203]: Audit report
                      - link "Open deck" [ref=e204] [cursor=pointer]:
                        - /url: /runs/R_core_api_001/deck
                        - generic [ref=e205]: Open deck
                      - link "Reading view" [ref=e206] [cursor=pointer]:
                        - /url: /artifacts/sha256:9836fd27dedc46ca60fa8a3939d39d8d4e5c99280149a8e16ada1791a7a2bc62?tab=content&view=reading
                        - generic [ref=e207]: Reading view
                      - link "replan" [ref=e208] [cursor=pointer]:
                        - /url: /compose?fromRun=R_core_api_001
                        - generic [ref=e209]: replan
                  - region "Epoch projection admission" [ref=e210]:
                    - generic [ref=e211]:
                      - generic [ref=e212]:
                        - term [ref=e213]: "Policy valid at:"
                        - definition [ref=e214]: unknown
                      - generic [ref=e215]:
                        - term [ref=e216]: "Knowledge tx at:"
                        - definition [ref=e217]: unknown
                      - generic [ref=e218]:
                        - term [ref=e219]: "Payload as of:"
                        - definition [ref=e220]: unknown
                      - generic [ref=e221]:
                        - term [ref=e222]: "Source as of:"
                        - definition [ref=e223]: unknown
                      - generic [ref=e224]:
                        - term [ref=e225]: "Observed at:"
                        - definition [ref=e226]: unknown
                      - generic [ref=e227]:
                        - term [ref=e228]: "Source state:"
                        - definition [ref=e229]: unknown
                      - generic [ref=e230]:
                        - term [ref=e231]: "Claim as of:"
                        - definition [ref=e232]: epoch_projection_not_established
                      - generic [ref=e233]:
                        - term [ref=e234]: "Epoch:"
                        - definition [ref=e235]: Epoch not established
                      - generic [ref=e236]:
                        - term [ref=e237]: "Epoch status:"
                        - definition [ref=e238]: not established
                      - generic [ref=e239]:
                        - term [ref=e240]: "Validity:"
                        - definition [ref=e241]: not established
                      - generic [ref=e242]:
                        - term [ref=e243]: "Revalidation:"
                        - definition [ref=e244]: not required
                      - generic [ref=e245]:
                        - term [ref=e246]: "Cache age:"
                        - definition [ref=e247]: unknown (unrecognized)
                    - paragraph [ref=e248]: Epoch projection could not be admitted; no currentness claim is made.
                  - generic [ref=e249]:
                    - article [ref=e250]:
                      - generic [ref=e252]: Started
                      - strong [ref=e253]: Sep 1, 2026, 9:54 PM
                      - generic [ref=e254]: "Duration: 0 ms"
                    - article [ref=e255]:
                      - generic [ref=e257]: Preflight
                      - strong [ref=e258]: Blocked
                      - generic [ref=e259]: 1 diagnostic
                    - article [ref=e260]:
                      - generic [ref=e262]: Evaluator
                      - strong [ref=e263]: REPLAN_DATA
                      - button "score 0.67 0.67, untraced provenance available, Freshness Unknown" [ref=e265]:
                        - generic [ref=e266]: "0.67"
                        - img [ref=e267]
                        - img [ref=e270]
                    - article [ref=e273]:
                      - generic [ref=e275]: Governance
                      - strong [ref=e276]:
                        - button "blockers 1 1 blockers, untraced provenance available, Freshness Unknown" [ref=e277]:
                          - generic [ref=e278]: "1"
                          - generic [ref=e279]: blockers
                          - img [ref=e280]
                          - img [ref=e283]
                      - generic [ref=e286]: blocked
                    - article [ref=e287]:
                      - generic [ref=e289]: Root artifacts
                      - strong [ref=e290]: "18"
                      - generic [ref=e291]: 23 linked artifacts
                - generic [ref=e293]:
                  - generic [ref=e294]:
                    - generic [ref=e295]:
                      - paragraph [ref=e296]: Decision packet
                      - heading "Verdict, uncertainty, and downstream posture" [level=3] [ref=e297]
                    - generic [ref=e298]: blocked
                  - generic [ref=e299]:
                    - article [ref=e300]:
                      - generic [ref=e302]: Verdict
                      - strong [ref=e303]: reject
                      - generic [ref=e304]: reject
                    - article [ref=e305]:
                      - generic [ref=e307]: Confidence
                      - strong [ref=e308]: Unknown
                      - generic [ref=e309]: Decision score
                    - article [ref=e310]:
                      - generic [ref=e312]: Blocker state
                      - strong [ref=e313]:
                        - button "Blocker state 1 blockers, untraced provenance available, Freshness Unknown" [ref=e314]:
                          - generic [ref=e315]: "1"
                          - generic [ref=e316]: blockers
                          - img [ref=e317]
                          - img [ref=e320]
                      - generic [ref=e323]: Governance
                  - generic [ref=e324]:
                    - generic [ref=e325]:
                      - paragraph [ref=e326]: Key impact deltas
                      - paragraph [ref=e328]:
                        - generic [ref=e329]: Operator.
                        - text: Runtime did not return impact deltas for this run packet.
                    - generic [ref=e330]:
                      - paragraph [ref=e331]: Strongest evidence
                      - strong [ref=e332]: Promotion lane signal
                      - paragraph [ref=e333]:
                        - generic [ref=e334]: Quoted text from worldbank.wdi / promotion_fixture_001.
                        - text: NY.GDP.MKTP.KD is queued on Explorelane with 87% confidence.
                        - link "Citation · worldbank.wdi / promotion_fixture_001" [ref=e336] [cursor=pointer]:
                          - /url: /evidence?artifactId=sha256%3A9836fd27dedc46ca60fa8a3939d39d8d4e5c99280149a8e16ada1791a7a2bc62&focus=artifact&runId=R_core_api_001
                          - generic [ref=e337]: Citation · worldbank.wdi / promotion_fixture_001
                    - generic [ref=e338]:
                      - paragraph [ref=e339]: Main uncertainty
                      - paragraph [ref=e340]:
                        - generic [ref=e341]: AI-generated by Formalizer.
                        - generic [ref=e342]: ≔
                        - text: Policy blocker
                  - generic [ref=e344]:
                    - generic [ref=e345]:
                      - paragraph [ref=e346]: Downstream dependencies
                      - paragraph [ref=e347]: Downstream dependencies
                    - generic [ref=e348]:
                      - generic [ref=e349]: Scientist.Decision Packet
                      - generic [ref=e350]: Scientist.Execution Plan
                      - generic [ref=e351]: pending promotion review
                      - generic [ref=e352]: blocked
                  - generic [ref=e353]:
                    - text: Unavailable
                    - list [ref=e354]:
                      - listitem [ref=e355]: Identifiability state is served on QuantityUncertainty and was bound correctly by the retired surface. The REMEDY — which dataset, RCT or instrument would repair it, and its acquisition ref — requires an acquisition planner that does not exist in the source tree.
                      - listitem [ref=e356]: No E-value estimator exists anywhere in the source tree, so neither the E-value nor the claim-extinction verdict derived from it has a producer.
                      - listitem [ref=e357]: Cohort transition analysis is resident offline and is not served per run; the retired timeline interpolated shares that no runtime computation produced.
                      - listitem [ref=e358]: No stress-scene or stress-ranking producer exists in the source tree; the retired ranking ordered scenes the surface itself invented.
                  - generic [ref=e359]:
                    - text: Unavailable
                    - list [ref=e360]:
                      - listitem [ref=e361]: No governed artifact defines how a readiness verdict is composed. The retired surface derived one from local thresholds, regexes, dwell state and disputes; the inputs are served by their own owners, the composition rule does not exist.
                      - listitem [ref=e362]: Stakeholder-lens projection is audience mapping, owned by the DS0/DS3 audience grammar. DS16 references that grammar and may not re-derive it.
                      - listitem [ref=e363]: Fairness analysis is resident in the offline scientist and foundry packages and has no presence in the HTTP runtime. Serving it would establish an analysis capability, which this slice explicitly does not claim.
                      - listitem [ref=e364]: Harm assessment is resident in the offline scientist and foundry packages and has no presence in the HTTP runtime. Serving it would establish an analysis capability, which this slice explicitly does not claim.
                      - listitem [ref=e365]: No embargo concept exists anywhere in the source tree under any name; the retired overlay was constructed entirely on the surface.
                      - listitem [ref=e366]: Slow-review requirements were derived from browser dwell state held in local storage. Dwell time is interaction state and never became a runtime value.
                      - listitem [ref=e367]: No revocation ledger exists. The one 'revocation' token in the served schema is a step-up authentication class on a reissue endpoint, an unrelated concept.
                  - generic [ref=e368]:
                    - generic [ref=e369]:
                      - generic [ref=e370]:
                        - paragraph [ref=e371]: Phase 3.5 / Explanation and publication
                        - heading "Signed publication packet" [level=3] [ref=e372]
                        - paragraph [ref=e373]: Decision, model card, coverage caveat, threshold contract, argument map, glossary and deterministic explanations are ready for a signed public viewer.
                      - generic [ref=e374]:
                        - generic "This frontend signature verifies packet integrity only; it is not trust, approval, publication, or closeout authority." [ref=e375]: sig:3c0d6fe1
                        - generic [ref=e376]:
                          - generic [ref=e377]: projection_absent
                          - generic [ref=e378]: Unavailable
                        - link "Open public viewer" [ref=e379] [cursor=pointer]:
                          - /url: /public/decisions/eyJwYWNrZXQiOnsiYXJndW1lbnRNYXAiOnsiZWRnZXMiOlt7ImZyb20iOiJncm91bmRzOlJfY29yZV9hcGlfMDAxOm1ldHJpY3MiLCJyZWxhdGlvbiI6Imdyb3VuZHMiLCJ0byI6ImNsYWltOlJfY29yZV9hcGlfMDAxOnZlcmRpY3QifSx7ImZyb20iOiJ3YXJyYW50OlJfY29yZV9hcGlfMDAxOnBvbGljeS1zdGFuZGFyZCIsInJlbGF0aW9uIjoid2FycmFudHMiLCJ0byI6ImNsYWltOlJfY29yZV9hcGlfMDAxOnZlcmRpY3QifSx7ImZyb20iOiJiYWNraW5nOlJfY29yZV9hcGlfMDAxOmV2aWRlbmNlIiwicmVsYXRpb24iOiJiYWNrcyIsInRvIjoid2FycmFudDpSX2NvcmVfYXBpXzAwMTpwb2xpY3ktc3RhbmRhcmQifSx7ImZyb20iOiJyZWJ1dHRhbDpSX2NvcmVfYXBpXzAwMTpnb3Zlcm5hbmNlIiwicmVsYXRpb24iOiJyZWJ1dHMiLCJ0byI6ImNsYWltOlJfY29yZV9hcGlfMDAxOnZlcmRpY3QifV0sIm5vZGVzIjpbeyJkZXRhaWwiOiJOL0EiLCJpZCI6ImNsYWltOlJfY29yZV9hcGlfMDAxOnZlcmRpY3QiLCJraW5kIjoiY2xhaW0iLCJsYWJlbCI6IlB1YmxpYyBkZWNpc2lvbjogb3duZXIgdmVyZGljdCByZWNvcmRlZCIsInJlZnMiOlsiUl9jb3JlX2FwaV8wMDEiXX0seyJkZXRhaWwiOiJBcHBsaWVkIE5vZGVzIGlzICsxLjAwLiIsImlkIjoiZ3JvdW5kczpSX2NvcmVfYXBpXzAwMTptZXRyaWNzIiwia2luZCI6Imdyb3VuZHMiLCJsYWJlbCI6IlB1Ymxpc2hlZCBncm91bmRzIiwicmVmcyI6WyJtZXRyaWM6QXBwbGllZF9Ob2RlcyIsIm1ldHJpYzpQb2xpY3lfQ29zdCJdfSx7ImRldGFpbCI6IlRoZSByZWNvbW1lbmRhdGlvbiBpcyB3YXJyYW50ZWQgb25seSB3aGVuIHRoZSBwdWJsaXNoZWQgbWV0cmljcywgdW5jZXJ0YWludHksIGNvdmVyYWdlIGFuZCBnb3Zlcm5hbmNlIHN0YXR1cyByZW1haW4gYWxpZ25lZC4iLCJpZCI6IndhcnJhbnQ6Ul9jb3JlX2FwaV8wMDE6cG9saWN5LXN0YW5kYXJkIiwia2luZCI6IndhcnJhbnQiLCJsYWJlbCI6IlBvbGljeSB3YXJyYW50IiwicmVmcyI6WyJhdGxhczpwdWJsaWNhdGlvbjp3YXJyYW50Il19LHsiZGV0YWlsIjoiVGhlIHB1YmxpYyBwYWNrZXQgY2l0ZXMgZXZpZGVuY2UgYXJ0aWZhY3RzIHdpdGhvdXQgZXhwb3NpbmcgcHJpdmF0ZSByYXcgY29udGV4dC4iLCJpZCI6ImJhY2tpbmc6Ul9jb3JlX2FwaV8wMDE6ZXZpZGVuY2UiLCJraW5kIjoiYmFja2luZyIsImxhYmVsIjoiRXZpZGVuY2UgYmFja2luZyIsInJlZnMiOlsic2hhMjU2Ojc5ODhiZDJiZDBhNzRhYzU0ZDQ1MGIyZDZhN2FjZTQ4ZmVkMWMyODdmMDgyNzljM2JmOWE3YTkzZmYzNzIwNDUiLCJzaGEyNTY6ZDVjZjg3YjE0NDk3YjFlOGE4NWJjMjBhM2E5OGM2OTgxMDZlNzc0MzEyMjU4YjdhMGFlMDhiZDY0ZThkZGU2NyIsInNoYTI1NjozMjZkNjBmMTc4NWRmZGZhY2Q3YTRmNTdmMGUwYmUxYWJiNTU1YzQ4MTdkMDcyZGNiMTIzYjMyYjlmZjFhYjNlIl19LHsiZGV0YWlsIjoiMSBwdWJsaWMgZ292ZXJuYW5jZSBpc3N1ZSByZWZlcmVuY2UocykgYXJlIGF0dGFjaGVkLiIsImlkIjoicmVidXR0YWw6Ul9jb3JlX2FwaV8wMDE6Z292ZXJuYW5jZSIsImtpbmQiOiJyZWJ1dHRhbCIsImxhYmVsIjoiR292ZXJuYW5jZSBpc3N1ZSByZWZlcmVuY2VzIiwicmVmcyI6WyJHT1YwMDEiXX1dLCJyb290Q2xhaW1JZCI6ImNsYWltOlJfY29yZV9hcGlfMDAxOnZlcmRpY3QifSwiYnVyZWF1Y3JhdGljRm9ybXMiOlt7ImFzdFBhdGNoQ29udHJhY3QiOiJidXJlYXVjcmF0aWNfYXN0X3BhdGNoLnYxIiwiZWRpdFN1cmZhY2VJZCI6ImZvcm1zLnVhLm5ha2F6LmVkaXQiLCJnZW5yZSI6Im5ha2F6IiwibGFiZWwiOiLQndCw0LrQsNC3IiwibGVnYWxPcmRlciI6WyJyZXF1aXNpdGVzIiwicHJlYW1ibGUiLCJvcmRlciIsImNvbnRyb2wiLCJzaWduYXR1cmUiXSwibG9jYWxlIjoidWstVUEiLCJyZW5kZXJTdXJmYWNlSWQiOiJmb3Jtcy51YS5uYWthei5yZW5kZXIifSx7ImFzdFBhdGNoQ29udHJhY3QiOiJidXJlYXVjcmF0aWNfYXN0X3BhdGNoLnYxIiwiZWRpdFN1cmZhY2VJZCI6ImZvcm1zLnVhLnJvenBvcmlhZHpoZW5uaWEuZWRpdCIsImdlbnJlIjoicm96cG9yaWFkemhlbm5pYSIsImxhYmVsIjoi0KDQvtC30L_QvtGA0Y_QtNC20LXQvdC90Y8iLCJsZWdhbE9yZGVyIjpbInJlcXVpc2l0ZXMiLCJsZWdhbF9iYXNpcyIsImRpcmVjdGl2ZSIsImV4ZWN1dGlvbiIsInNpZ25hdHVyZSJdLCJsb2NhbGUiOiJ1ay1VQSIsInJlbmRlclN1cmZhY2VJZCI6ImZvcm1zLnVhLnJvenBvcmlhZHpoZW5uaWEucmVuZGVyIn0seyJhc3RQYXRjaENvbnRyYWN0IjoiYnVyZWF1Y3JhdGljX2FzdF9wYXRjaC52MSIsImVkaXRTdXJmYWNlSWQiOiJmb3Jtcy51YS5wb3N0YW5vdmEuZWRpdCIsImdlbnJlIjoicG9zdGFub3ZhIiwibGFiZWwiOiLQn9C-0YHRgtCw0L3QvtCy0LAiLCJsZWdhbE9yZGVyIjpbInJlcXVpc2l0ZXMiLCJwcmVhbWJsZSIsIm9wZXJhdGl2ZV9wYXJ0IiwiYW5uZXhlcyIsInNpZ25hdHVyZSJdLCJsb2NhbGUiOiJ1ay1VQSIsInJlbmRlclN1cmZhY2VJZCI6ImZvcm1zLnVhLnBvc3Rhbm92YS5yZW5kZXIifSx7ImFzdFBhdGNoQ29udHJhY3QiOiJidXJlYXVjcmF0aWNfYXN0X3BhdGNoLnYxIiwiZWRpdFN1cmZhY2VJZCI6ImZvcm1zLnVhLnZ5c25vdm9rLmVkaXQiLCJnZW5yZSI6InZ5c25vdm9rIiwibGFiZWwiOiLQktC40YHQvdC-0LLQvtC6IiwibGVnYWxPcmRlciI6WyJyZXF1aXNpdGVzIiwicXVlc3Rpb24iLCJhbmFseXNpcyIsImV2aWRlbmNlIiwiY29uY2x1c2lvbiIsInNpZ25hdHVyZSJdLCJsb2NhbGUiOiJ1ay1VQSIsInJlbmRlclN1cmZhY2VJZCI6ImZvcm1zLnVhLnZ5c25vdm9rLnJlbmRlciJ9XSwiY29tcHJlaGVuc2lvbiI6W3siZnJlc2huZXNzIjoiMTk3MC0wMS0wMVQwMDowMDowMC4wMDBaIiwiaWQiOiJwaGFzZTM1LmFyZ3VtZW50TWFwIiwiaW50ZW50IjoiU2hvd3MgY2xhaW0sIGdyb3VuZHMsIHdhcnJhbnQsIGJhY2tpbmcgYW5kIHJlYnV0dGFsIGFzIG9uZSBhdWRpdGFibGUgYXJndW1lbnQgcGF0aC4iLCJsYWJlbCI6IkFyZ3VtZW50IG1hcCIsInByb3ZlbmFuY2UiOiJSX2NvcmVfYXBpXzAwMSJ9LHsiZnJlc2huZXNzIjoiMTk3MC0wMS0wMVQwMDowMDowMC4wMDBaIiwiaWQiOiJwaGFzZTM1LmRldGVybWluaXN0aWNFeHBsYW5hdGlvbnMiLCJpbnRlbnQiOiJUdXJucyBkZWNpc2lvbi1iZWFyaW5nIG51bWJlcnMgaW50byByZXByb2R1Y2libGUgbm9uLUxMTSBleHBsYW5hdGlvbnMuIiwibGFiZWwiOiJEZXRlcm1pbmlzdGljIGV4cGxhbmF0aW9ucyIsInByb3ZlbmFuY2UiOiIyIGV4cGxhbmF0aW9uIHBhcnRzIn0seyJmcmVzaG5lc3MiOiIxOTcwLTAxLTAxVDAwOjAwOjAwLjAwMFoiLCJpZCI6InBoYXNlMzUucHVibGljVmlld2VyIiwiaW50ZW50IjoiUHJlc2VudHMgb25seSBzaWduZWQgcHVibGljIHBhY2tldCBkYXRhOyBubyBwcml2aWxlZ2VkIEFQSSBjb250ZXh0IGlzIHJlcXVpcmVkLiIsImxhYmVsIjoiUHVibGljIHZpZXdlciIsInByb3ZlbmFuY2UiOiJSX2NvcmVfYXBpXzAwMSJ9XSwiY29uZmlkZW5jZUxhZGRlciI6W3siaWQiOiJsYWRkZXI6Ul9jb3JlX2FwaV8wMDE6b3duZXItY29uZmlkZW5jZSIsImxhYmVsIjoiT3duZXIgY29uZmlkZW5jZSB1bmF2YWlsYWJsZSIsInJlYXNvbiI6Ik5vIG93bmVyLWlzc3VlZCBjb25maWRlbmNlIHF1YW50aXR5IHdhcyBzdXBwbGllZDsgYWJzZW5jZSByZW1haW5zIHVua25vd24uIiwicnVuZyI6bnVsbCwic2NvcmUiOnsibGFiZWwiOiJPd25lciBjb25maWRlbmNlIHF1YW50aXR5IiwibGluZWFnZSI6eyJjb21wYWN0X3N1bW1hcnkiOlt7ImtpbmQiOiJyZXN1bHQiLCJsYWJlbCI6Ik93bmVyIGNvbmZpZGVuY2UgcXVhbnRpdHkifV0sImZyZXNobmVzcyI6InVua25vd24iLCJpZCI6InVudHJhY2VkIiwicmVhc29uX2NvZGUiOiJvd25lcl9jb25maWRlbmNlX3F1YW50aXR5X2Fic2VudCIsInN0YXR1cyI6InVudHJhY2VkIiwidHJhY2tpbmdfaXNzdWUiOiJBVExBUy1EUzQtQzA2In0sIm1ldHJpY19pZCI6InB1YmxpYy5jb25maWRlbmNlX2xhZGRlci5vd25lcl9jb25maWRlbmNlLnNjb3JlIiwicG9pbnQiOm51bGwsInF1YW50aXR5X2NsYXNzIjoiZGVjaXNpb24iLCJ0aW1lIjpudWxsLCJ1bmNlcnRhaW50eSI6bnVsbCwidW5pdCI6eyJjb2RlIjoiMSIsImRpc3BsYXkiOiJyYXRpbyIsInN5c3RlbSI6InVjdW0ifX0sInRhcmdldFJlZiI6IlJfY29yZV9hcGlfMDAxIn1dLCJjb3ZlcmFnZUNhdmVhdCI6eyJjYXZlYXRTdGF0ZSI6eyJhdXRob3JpdHlQdXJwb3NlIjoiY2FuZGlkYXRlX2Rpc3BsYXkiLCJsYWJlbCI6ImNsZWFyIiwicHVycG9zZSI6ImludGVyYWN0aW9uX29ubHkifSwicmVnaW9ucyI6W3siY2F2ZWF0IjoiQ2FsY3VsYXRlZCBjb3ZlcmFnZSBmYWxscyBpbiB0aGUgbWlkZGxlIGRpc3BsYXkgYmFuZDsgaW5zcGVjdCB0aGUgc291cmNlIHJlZmVyZW5jZXMuIiwiZGVuc2l0eSI6MC42NDQ5OTk5OTk5OTk5OTk5LCJkaXNwbGF5U3RhdGUiOnsiYXV0aG9yaXR5UHVycG9zZSI6ImNhbmRpZGF0ZV9kaXNwbGF5IiwibGFiZWwiOiJtZWRpdW0iLCJwdXJwb3NlIjoiaW50ZXJhY3Rpb25fb25seSJ9LCJldmlkZW5jZVJlZnMiOlsicGxhbl9maXh0dXJlX2ZldGNoXzAwMSJdLCJsYWJlbCI6IlVTQSJ9XSwic3VtbWFyeSI6Ik5vIGNhbGN1bGF0ZWQgY292ZXJhZ2UgZGlzcGxheSBpcyBpbiB0aGUgbG93IGJhbmQ7IG93bmVyIHB1YmxpY2F0aW9uIHNlbWFudGljcyBhcmUgbm90IGluZmVycmVkLiJ9LCJkZWNpc2lvbiI6eyJjb25maWRlbmNlIjpudWxsLCJnZW5lcmF0ZWRBdCI6bnVsbCwiaGVhZGxpbmUiOiJQdWJsaWMgZGVjaXNpb246IG93bmVyIHZlcmRpY3QgcmVjb3JkZWQiLCJwb2xpY3lTdW1tYXJ5IjoiTi9BIiwicnVuSWQiOiJSX2NvcmVfYXBpXzAwMSIsInZlcmRpY3QiOiJyZWplY3QifSwiZGV0ZXJtaW5pc3RpY0V4cGxhbmF0aW9ucyI6W3siZGVyaXZhdGlvblBhdGgiOlt7ImRldGFpbCI6IlB1Ymxpc2hlZCBzb3VyY2UgZXZpZGVuY2UgZW50ZXJzIHRoZSBwdWJsaWMgcGFja2V0IGFzIGEgcmVmLiIsImlkIjoiZGVyaXZlOjA6c291cmNlIiwia2luZCI6InNvdXJjZSIsImxhYmVsIjoic2hhMjU2OmQ1Y2Y4N2IxNDQ5N2IxZThhODViYzIwYTNhOThjNjk4MTA2ZTc3NDMxMjI1OGI3YTBhZTA4YmQ2NGU4ZGRlNjcifSx7ImRldGFpbCI6IkV2aWRlbmNlIGJ1bmRsZSBiaW5kcyBzb3VyY2UgcmVmcyB0byBkZWNpc2lvbiBtZXRyaWNzLiIsImlkIjoiZGVyaXZlOjA6YXJ0aWZhY3QiLCJraW5kIjoiYXJ0aWZhY3QiLCJsYWJlbCI6InNoYTI1Njo3OTg4YmQyYmQwYTc0YWM1NGQ0NTBiMmQ2YTdhY2U0OGZlZDFjMjg3ZjA4Mjc5YzNiZjlhN2E5M2ZmMzcyMDQ1In0seyJkZXRhaWwiOiJNb2RlbCBvdXRwdXQgcmVwb3J0cyB0aGUgcG9pbnQgZXN0aW1hdGUgYW5kIGludGVydmFsLiIsImlkIjoiZGVyaXZlOjA6bW9kZWwiLCJraW5kIjoibW9kZWwiLCJsYWJlbCI6IkFwcGxpZWQgTm9kZXMifSx7ImRldGFpbCI6IlB1YmxpY2F0aW9uIGFkYXB0ZXIgcmVuZGVycyB0aGUgc2FtZSBwYXJ0cyBhcyBkZXRlcm1pbmlzdGljIHByb3NlLiIsImlkIjoiZGVyaXZlOjA6cHVibGljYXRpb24iLCJraW5kIjoidHJhbnNmb3JtIiwibGFiZWwiOiJwdWJsaWNhdGlvbiBuYXJyYXRpdmUifV0sImlkIjoiZXhwbGFuYXRpb246Ul9jb3JlX2FwaV8wMDE6MSIsImxhYmVsIjoiQXBwbGllZCBOb2RlcyIsIm5hcnJhdGl2ZSI6IkFwcGxpZWQgTm9kZXMgaXMgKzEuMDAgYmVjYXVzZSB0aGUgcHVibGljIHBvaW50IGVzdGltYXRlIGNhcnJpZXMgNzAlIG9mIHRoZSBleHBsYW5hdGlvbiwgdW5jZXJ0YWludHkgY2FycmllcyAxMCUgKG5vIHB1YmxpYyBpbnRlcnZhbCksIGFuZCBwdWJsaWMgcHJvdmVuYW5jZSBjYXJyaWVzIDIwJS4iLCJwYXJ0cyI6W3siY29udHJpYnV0aW9uU2hhcmUiOjAuNywibGFiZWwiOiJwb2ludCBlc3RpbWF0ZSIsInZhbHVlIjoiKzEuMDAifSx7ImNvbnRyaWJ1dGlvblNoYXJlIjowLjEsImxhYmVsIjoidW5jZXJ0YWludHkiLCJ2YWx1ZSI6Im5vIHB1YmxpYyBpbnRlcnZhbCJ9LHsiY29udHJpYnV0aW9uU2hhcmUiOjAuMiwibGFiZWwiOiJwdWJsaWMgcHJvdmVuYW5jZSIsInZhbHVlIjoic2hhMjU2Ojc5ODhiZDJiZDBhNzRhYzU0ZDQ1MGIyZDZhN2FjZTQ4ZmVkMWMyODdmMDgyNzljM2JmOWE3YTkzZmYzNzIwNDUifV0sInF1YW50aXR5Ijp7ImxhYmVsIjoiQXBwbGllZCBOb2RlcyIsImxpbmVhZ2UiOnsiY29tcGFjdF9zdW1tYXJ5IjpbeyJraW5kIjoicmVzdWx0IiwibGFiZWwiOiJBcHBsaWVkIE5vZGVzIn1dLCJmcmVzaG5lc3MiOiJ1bmtub3duIiwiaWQiOiJ1bnRyYWNlZCIsInJlYXNvbl9jb2RlIjoicHVibGljX3Byb2plY3Rpb25fd2l0aG91dF9ydW50aW1lX3F1YW50aXR5Iiwic3RhdHVzIjoidW50cmFjZWQiLCJ0cmFja2luZ19pc3N1ZSI6IkFUTEFTLURTNC1DMDYifSwibWV0cmljX2lkIjoicHVibGljLmRlY2lzaW9uX21ldHJpYy4xIiwicG9pbnQiOjEsInF1YW50aXR5X2NsYXNzIjoiZGVjaXNpb24iLCJ0aW1lIjpudWxsLCJ1bmNlcnRhaW50eSI6bnVsbCwidW5pdCI6eyJjb2RlIjoiMSIsImRpc3BsYXkiOiJ2YWx1ZSIsInN5c3RlbSI6InVjdW0ifX0sInN1YmplY3RSZWYiOiJtZXRyaWM6QXBwbGllZF9Ob2RlcyJ9LHsiZGVyaXZhdGlvblBhdGgiOlt7ImRldGFpbCI6IlB1Ymxpc2hlZCBzb3VyY2UgZXZpZGVuY2UgZW50ZXJzIHRoZSBwdWJsaWMgcGFja2V0IGFzIGEgcmVmLiIsImlkIjoiZGVyaXZlOjE6c291cmNlIiwia2luZCI6InNvdXJjZSIsImxhYmVsIjoic2hhMjU2OmQ1Y2Y4N2IxNDQ5N2IxZThhODViYzIwYTNhOThjNjk4MTA2ZTc3NDMxMjI1OGI3YTBhZTA4YmQ2NGU4ZGRlNjcifSx7ImRldGFpbCI6IkV2aWRlbmNlIGJ1bmRsZSBiaW5kcyBzb3VyY2UgcmVmcyB0byBkZWNpc2lvbiBtZXRyaWNzLiIsImlkIjoiZGVyaXZlOjE6YXJ0aWZhY3QiLCJraW5kIjoiYXJ0aWZhY3QiLCJsYWJlbCI6InNoYTI1Njo3OTg4YmQyYmQwYTc0YWM1NGQ0NTBiMmQ2YTdhY2U0OGZlZDFjMjg3ZjA4Mjc5YzNiZjlhN2E5M2ZmMzcyMDQ1In0seyJkZXRhaWwiOiJNb2RlbCBvdXRwdXQgcmVwb3J0cyB0aGUgcG9pbnQgZXN0aW1hdGUgYW5kIGludGVydmFsLiIsImlkIjoiZGVyaXZlOjE6bW9kZWwiLCJraW5kIjoibW9kZWwiLCJsYWJlbCI6IlBvbGljeSBDb3N0In0seyJkZXRhaWwiOiJQdWJsaWNhdGlvbiBhZGFwdGVyIHJlbmRlcnMgdGhlIHNhbWUgcGFydHMgYXMgZGV0ZXJtaW5pc3RpYyBwcm9zZS4iLCJpZCI6ImRlcml2ZToxOnB1YmxpY2F0aW9uIiwia2luZCI6InRyYW5zZm9ybSIsImxhYmVsIjoicHVibGljYXRpb24gbmFycmF0aXZlIn1dLCJpZCI6ImV4cGxhbmF0aW9uOlJfY29yZV9hcGlfMDAxOjIiLCJsYWJlbCI6IlBvbGljeSBDb3N0IiwibmFycmF0aXZlIjoiUG9saWN5IENvc3QgaXMgKzEwMC4wMCBiZWNhdXNlIHRoZSBwdWJsaWMgcG9pbnQgZXN0aW1hdGUgY2FycmllcyA3MCUgb2YgdGhlIGV4cGxhbmF0aW9uLCB1bmNlcnRhaW50eSBjYXJyaWVzIDEwJSAobm8gcHVibGljIGludGVydmFsKSwgYW5kIHB1YmxpYyBwcm92ZW5hbmNlIGNhcnJpZXMgMjAlLiIsInBhcnRzIjpbeyJjb250cmlidXRpb25TaGFyZSI6MC43LCJsYWJlbCI6InBvaW50IGVzdGltYXRlIiwidmFsdWUiOiIrMTAwLjAwIn0seyJjb250cmlidXRpb25TaGFyZSI6MC4xLCJsYWJlbCI6InVuY2VydGFpbnR5IiwidmFsdWUiOiJubyBwdWJsaWMgaW50ZXJ2YWwifSx7ImNvbnRyaWJ1dGlvblNoYXJlIjowLjIsImxhYmVsIjoicHVibGljIHByb3ZlbmFuY2UiLCJ2YWx1ZSI6InNoYTI1Njo3OTg4YmQyYmQwYTc0YWM1NGQ0NTBiMmQ2YTdhY2U0OGZlZDFjMjg3ZjA4Mjc5YzNiZjlhN2E5M2ZmMzcyMDQ1In1dLCJxdWFudGl0eSI6eyJsYWJlbCI6IlBvbGljeSBDb3N0IiwibGluZWFnZSI6eyJjb21wYWN0X3N1bW1hcnkiOlt7ImtpbmQiOiJyZXN1bHQiLCJsYWJlbCI6IlBvbGljeSBDb3N0In1dLCJmcmVzaG5lc3MiOiJ1bmtub3duIiwiaWQiOiJ1bnRyYWNlZCIsInJlYXNvbl9jb2RlIjoicHVibGljX3Byb2plY3Rpb25fd2l0aG91dF9ydW50aW1lX3F1YW50aXR5Iiwic3RhdHVzIjoidW50cmFjZWQiLCJ0cmFja2luZ19pc3N1ZSI6IkFUTEFTLURTNC1DMDYifSwibWV0cmljX2lkIjoicHVibGljLmRlY2lzaW9uX21ldHJpYy4yIiwicG9pbnQiOjEwMCwicXVhbnRpdHlfY2xhc3MiOiJkZWNpc2lvbiIsInRpbWUiOm51bGwsInVuY2VydGFpbnR5IjpudWxsLCJ1bml0Ijp7ImNvZGUiOiIxIiwiZGlzcGxheSI6InZhbHVlIiwic3lzdGVtIjoidWN1bSJ9fSwic3ViamVjdFJlZiI6Im1ldHJpYzpQb2xpY3lfQ29zdCJ9XSwiZXBvY2hTZW1hbnRpY3MiOnsiYXNPZiI6bnVsbCwiYXNPZlJlYXNvbiI6ImVwb2NoX3Byb2plY3Rpb25fbm90X2VzdGFibGlzaGVkIiwiY3VycmVudEVwb2NoUmVmIjpudWxsLCJlcG9jaFJlZnMiOltdLCJraW5kIjoibm9ucmVjZWlwdCIsInByb2plY3Rpb25TZW1hbnRpY0hhc2giOm51bGwsInJldmFsaWRhdGlvblJlcXVpcmVkIjpmYWxzZSwic3RhdHVzIjoibm90X2VzdGFibGlzaGVkIiwidmFsaWRpdHlTdGF0dXMiOm51bGx9LCJnbG9zc2FyeSI6W3siZGVmaW5pdGlvbiI6IkEgZGVjaXNpb24tYmVhcmluZyByZWNvcmQgdGhhdCBrZWVwcyBvdXRjb21lLCBldmlkZW5jZSwgdW5jZXJ0YWludHksIHByb3ZlbmFuY2UgYW5kIHJldmlldyBzdGF0dXMgdG9nZXRoZXIuIiwiZml4ZWRBdCI6IjIwMjYtMDQtMjkiLCJvd25lciI6IkF0bGFzIGRlc2lnbiBzeXN0ZW0iLCJwcm92ZW5hbmNlUmVmIjoiZG9jcy9icmFuZC9BVExBU19ERVNJR05fU1lTVEVNLm1kI2RlY2lzaW9uLXBhY2tldCIsInRlcm0iOiJkZWNpc2lvbiBwYWNrZXQifSx7ImRlZmluaXRpb24iOiJBIHRyYWNlIGZyb20gc291cmNlIGRhdGEgdGhyb3VnaCB0cmFuc2Zvcm1hdGlvbnMsIG1vZGVsIG91dHB1dCBhbmQgYXJ0aWZhY3QgcHVibGljYXRpb24uIiwiZml4ZWRBdCI6IjIwMjYtMDQtMjkiLCJvd25lciI6IkV2aWRlbmNlIEZhYnJpYyIsInByb3ZlbmFuY2VSZWYiOiJkb2NzL2JyYW5kL0FUTEFTX0RFU0lHTl9TWVNURU0ubWQjcHJvdmVuYW5jZSIsInRlcm0iOiJwcm92ZW5hbmNlIn0seyJkZWZpbml0aW9uIjoiQSBjb25maWRlbmNlLCBpbnRlcnZhbCBvciBpZGVudGlmaWFiaWxpdHkgbWFya2VyIHRoYXQgY2hhbmdlcyBob3cgc3Ryb25nbHkgYSBjbGFpbSBjYW4gYmUgdXNlZC4iLCJmaXhlZEF0IjoiMjAyNi0wNC0yOSIsIm93bmVyIjoiU2NpZW50aXN0IGxheWVyIiwicHJvdmVuYW5jZVJlZiI6ImRvY3MvYnJhbmQvQVRMQVNfREVTSUdOX1NZU1RFTS5tZCN1bmNlcnRhaW50eSIsInRlcm0iOiJ1bmNlcnRhaW50eSJ9LHsiZGVmaW5pdGlvbiI6IkEgcG9saWN5IGN1dG9mZiBjb250cmFjdCB0aGF0IGV4cG9zZXMgdGhlIHRocmVzaG9sZCwgZWRnZSBjYXNlcyBhbmQgY2FsaWJyYXRpb24gY2F2ZWF0LiIsImZpeGVkQXQiOiIyMDI2LTA0LTI5Iiwib3duZXIiOiJQb2xpY3lPUyBnb3Zlcm5hbmNlIiwicHJvdmVuYW5jZVJlZiI6ImRvY3MvcGxhbnMvYWN0aXZlL0RFU0lHTl9CRVNUX0lOX0NMQVNTX1BMQU4ubWQjZjQiLCJ0ZXJtIjoidGhyZXNob2xkIG1pY3JvY29udHJhY3QifSx7ImRlZmluaXRpb24iOiJBIHB1YmxpYyB3YXJuaW5nIGF0dGFjaGVkIHdoZW4gYWZmZWN0ZWQgZ2VvZ3JhcGh5IG9yIGNvaG9ydCBldmlkZW5jZSBpcyBzcGFyc2UuIiwiZml4ZWRBdCI6IjIwMjYtMDQtMjkiLCJvd25lciI6IkV2aWRlbmNlIEZhYnJpYyIsInByb3ZlbmFuY2VSZWYiOiJkb2NzL3BsYW5zL2FjdGl2ZS9ERVNJR05fQkVTVF9JTl9DTEFTU19QTEFOLm1kI2YzIiwidGVybSI6ImNvdmVyYWdlIGNhdmVhdCJ9XSwibW9kZWxDYXJkIjp7Im1vZGVsSWQiOiJtb2RlbDpSX2NvcmVfYXBpXzAwMSIsInJlZmVyZW5jZXMiOlt7ImlkIjoicmVmOm1vZGVsIiwibGFiZWwiOiJQb2xpY3lPUyBkZWNpc2lvbiBtb2RlbCIsImxvY2F0b3IiOiJtb2RlbDpSX2NvcmVfYXBpXzAwMSIsInR5cGUiOiJtb2RlbCJ9LHsiaWQiOiJyZWY6YXJ0aWZhY3Q6MSIsImxhYmVsIjoiZmFicmljLmV2aWRlbmNlX2J1bmRsZSIsImxvY2F0b3IiOiJzaGEyNTY6Nzk4OGJkMmJkMGE3NGFjNTRkNDUwYjJkNmE3YWNlNDhmZWQxYzI4N2YwODI3OWMzYmY5YTdhOTNmZjM3MjA0NSIsInR5cGUiOiJhcnRpZmFjdCJ9LHsiaWQiOiJyZWY6YXJ0aWZhY3Q6MiIsImxhYmVsIjoiZmFicmljLmRhdGFfc25hcHNob3QiLCJsb2NhdG9yIjoic2hhMjU2OmQ1Y2Y4N2IxNDQ5N2IxZThhODViYzIwYTNhOThjNjk4MTA2ZTc3NDMxMjI1OGI3YTBhZTA4YmQ2NGU4ZGRlNjciLCJ0eXBlIjoiYXJ0aWZhY3QifSx7ImlkIjoicmVmOmFydGlmYWN0OjMiLCJsYWJlbCI6ImZvdW5kcnkuaW5wdXRfYmluZGluZ3MiLCJsb2NhdG9yIjoic2hhMjU2OjMyNmQ2MGYxNzg1ZGZkZmFjZDdhNGY1N2YwZTBiZTFhYmI1NTVjNDgxN2QwNzJkY2IxMjNiMzJiOWZmMWFiM2UiLCJ0eXBlIjoiYXJ0aWZhY3QifV0sInNlY3Rpb25zIjpbeyJib2R5IjoiVGhpcyBjYXJkIGRvY3VtZW50cyB0aGUgcHVibGljLWZhY2luZyBtb2RlbCBiZWhhdmlvciB1c2VkIGZvciB0aGUgZGVjaXNpb24gcGFja2V0LiIsImZvb3Rub3RlUmVmcyI6WyJyZWY6bW9kZWwiXSwiaWQiOiJpbnRlbmRlZC11c2UiLCJwcm92ZW5hbmNlUmVmcyI6WyJSX2NvcmVfYXBpXzAwMSJdLCJ0aXRsZSI6IkludGVuZGVkIHVzZSJ9LHsiYm9keSI6IlB1Ymxpc2hlZCBtZXRyaWNzOiBBcHBsaWVkIE5vZGVzLCBQb2xpY3kgQ29zdC4iLCJmb290bm90ZVJlZnMiOlsicmVmOmFydGlmYWN0OjEiLCJyZWY6YXJ0aWZhY3Q6MiIsInJlZjphcnRpZmFjdDozIl0sImlkIjoiaW5wdXRzIiwicHJvdmVuYW5jZVJlZnMiOlsibW9kZWw6Ul9jb3JlX2FwaV8wMDEiLCJzaGEyNTY6Nzk4OGJkMmJkMGE3NGFjNTRkNDUwYjJkNmE3YWNlNDhmZWQxYzI4N2YwODI3OWMzYmY5YTdhOTNmZjM3MjA0NSIsInNoYTI1NjpkNWNmODdiMTQ0OTdiMWU4YTg1YmMyMGEzYTk4YzY5ODEwNmU3NzQzMTIyNThiN2EwYWUwOGJkNjRlOGRkZTY3Iiwic2hhMjU2OjMyNmQ2MGYxNzg1ZGZkZmFjZDdhNGY1N2YwZTBiZTFhYmI1NTVjNDgxN2QwNzJkY2IxMjNiMzJiOWZmMWFiM2UiXSwidGl0bGUiOiJJbnB1dHMgYW5kIGV2aWRlbmNlIn0seyJib2R5IjoiVGhlIG93bmVyLXJlY29yZGVkIGRlY2lzaW9uIGdyYWRlIGlzIHJlamVjdDsgdGhlIHJlY29yZGVkIGNvbmZpZGVuY2UgbGFiZWwgaXMgdW5hdmFpbGFibGUuIiwiZm9vdG5vdGVSZWZzIjpbInJlZjptb2RlbCJdLCJpZCI6InZhbGlkYXRpb24iLCJwcm92ZW5hbmNlUmVmcyI6WyJSX2NvcmVfYXBpXzAwMSJdLCJ0aXRsZSI6IlZhbGlkYXRpb24ifSx7ImJvZHkiOiJSZXN0cmljdGVkIG5vdGVzLCByYXcgdmFsdWVzIGFuZCBlbWJhcmdvZWQgZXZpZGVuY2UgYXJlIGV4Y2x1ZGVkIGZyb20gdGhpcyBwdWJsaWMgY2FyZC4iLCJmb290bm90ZVJlZnMiOltdLCJpZCI6ImxpbWl0YXRpb25zIiwicHJvdmVuYW5jZVJlZnMiOlsiYXRsYXM6cHVibGljLXJlZGFjdGlvbiJdLCJ0aXRsZSI6IkxpbWl0YXRpb25zIn1dLCJ0aXRsZSI6IkNpdGF0aW9uLWdyYWRlIG1vZGVsIGNhcmQifSwicGFja2V0SGFzaCI6InB1Yjo5MjUyNmE1NyIsInByb2plY3Rpb25TZW1hbnRpY3MiOnsiYXV0aG9yaXR5Um9sZSI6bnVsbCwiY2xvc2VvdXRUcnV0aCI6bnVsbCwiZGlzcGxheVN0YXRlcyI6W3siYXV0aG9yaXR5UHVycG9zZSI6ImNhbmRpZGF0ZV9kaXNwbGF5IiwibGFiZWwiOiJwcm9qZWN0aW9uX2Fic2VudCIsInB1cnBvc2UiOiJpbnRlcmFjdGlvbl9vbmx5In1dLCJldmlkZW5jZUNsYXNzIjpudWxsLCJnZW5lcmF0ZWRBdCI6bnVsbCwibWF5Tm90QmVVc2VkRm9yIjpbImFwcHJvdmFsX2F1dGhvcml0eSIsInJlYWRpbmVzc19hdXRob3JpdHkiLCJydW50aW1lX2Nsb3Nlb3V0X2F1dGhvcml0eSIsInNjb3JlY2FyZF9hdXRob3JpdHkiXSwicHJpbWFyeURpc3BsYXlTdGF0ZSI6eyJhdXRob3JpdHlQdXJwb3NlIjoiY2FuZGlkYXRlX2Rpc3BsYXkiLCJsYWJlbCI6InByb2plY3Rpb25fYWJzZW50IiwicHVycG9zZSI6ImludGVyYWN0aW9uX29ubHkifSwicHJvamVjdGlvblBvbGljeSI6bnVsbCwicHJvdmVuYW5jZUtpbmQiOm51bGwsInN1cmZhY2UiOm51bGx9LCJzY2hlbWEiOiJwb2xpc3lvcy5wdWJsaWNfZGVjaXNpb25fcGFja2V0LnYxIiwidGhyZXNob2xkQ29udHJhY3QiOnsiYWJvdmVDb3VudCI6bnVsbCwiYmVsb3dDb3VudCI6bnVsbCwiY2FsaWJyYXRpb25DYXZlYXQiOiJEZWNpc2lvbiB0aHJlc2hvbGQgcHJveGltaXR5IGlzIHVuYXZhaWxhYmxlIHVudGlsIGEgcHJvZHVjZXIgdGhyZXNob2xkIGNvbnRyYWN0IGlzIHN1cHBsaWVkLiIsImVkZ2VDYXNlcyI6W10sImVwc2lsb24iOm51bGwsIm5lYXJMaW5lQ291bnQiOm51bGwsInBvbGljeVJlZiI6InBvbGljeTpSX2NvcmVfYXBpXzAwMSIsInRocmVzaG9sZCI6bnVsbH0sInRydXN0RnJhbWluZyI6eyJhdXRob3JpdHlSb2xlIjoibm90X2Nsb3Nlb3V0X2F1dGhvcml0eSIsImNsb3Nlb3V0QXV0aG9yaXR5Q2F2ZWF0IjoiRnJvbnRlbmQgc2lnbmF0dXJlcywgYmFkZ2VzLCBsYWJlbHMsIGFuZCBwcm9qZWN0aW9ucyBhcmUgbm90IGNsb3Nlb3V0IGF1dGhvcml0eS4iLCJpbnRlZ3JpdHlTaWduYXR1cmVOb3RpY2UiOnsiYXV0aG9yaXR5Q2F2ZWF0IjoiVGhpcyBmcm9udGVuZCBzaWduYXR1cmUgdmVyaWZpZXMgcGFja2V0IGludGVncml0eSBvbmx5OyBpdCBpcyBub3QgdHJ1c3QsIGFwcHJvdmFsLCBwdWJsaWNhdGlvbiwgb3IgY2xvc2VvdXQgYXV0aG9yaXR5LiIsImJhZGdlIjoiSW50ZWdyaXR5IG9ubHkiLCJsYWJlbCI6IkZyb250ZW5kIGludGVncml0eSBzaWduYXR1cmUiLCJzaWduYXR1cmVDdWUiOiJmcm9udGVuZF9pbnRlZ3JpdHlfc2lnbmF0dXJlX25vdF9hdXRob3JpdGF0aXZlIn0sIm1heU5vdEJlVXNlZEZvciI6WyJhcHByb3ZhbF9hdXRob3JpdHkiLCJyZWFkaW5lc3NfYXV0aG9yaXR5IiwicnVudGltZV9jbG9zZW91dF9hdXRob3JpdHkiLCJzY29yZWNhcmRfYXV0aG9yaXR5Il0sInNjZW5hcmlvQ2F2ZWF0cyI6W10sInZpc2libGVDYXZlYXQiOiJVc2UgcnVudGltZSBzY29yZWNhcmQvcmVhZGluZXNzIGF1dGhvcml0eSBiZWZvcmUgYXBwcm92YWwgb3IgY2xvc2VvdXQuIn19LCJzaWduYXR1cmUiOiJzaWc6M2MwZDZmZTEifQ.3c0d6fe1
                          - generic [ref=e380]:
                            - img [ref=e381]
                            - text: Open public viewer
                    - generic [ref=e386]:
                      - generic [ref=e387]:
                        - paragraph [ref=e388]: Signed decision
                        - 'heading "Public decision: owner verdict recorded" [level=4] [ref=e389]'
                        - paragraph [ref=e390]: N/A
                      - generic [ref=e391]:
                        - generic [ref=e392]: pub:92526a57
                        - generic [ref=e393]: Unknown
                    - generic [ref=e395]:
                      - generic [ref=e396]:
                        - term [ref=e397]: "Policy valid at:"
                        - definition [ref=e398]: unknown
                      - generic [ref=e399]:
                        - term [ref=e400]: "Knowledge tx at:"
                        - definition [ref=e401]: unknown
                      - generic [ref=e402]:
                        - term [ref=e403]: "Payload as of:"
                        - definition [ref=e404]: unknown
                      - generic [ref=e405]:
                        - term [ref=e406]: "Source as of:"
                        - definition [ref=e407]: unknown
                      - generic [ref=e408]:
                        - term [ref=e409]: "Observed at:"
                        - definition [ref=e410]: unknown
                      - generic [ref=e411]:
                        - term [ref=e412]: "Source state:"
                        - definition [ref=e413]: unknown
                      - generic [ref=e414]:
                        - term [ref=e415]: "Claim as of:"
                        - definition [ref=e416]: epoch_projection_not_established
                      - generic [ref=e417]:
                        - term [ref=e418]: "Epoch:"
                        - definition [ref=e419]: Epoch not established
                      - generic [ref=e420]:
                        - term [ref=e421]: "Epoch status:"
                        - definition [ref=e422]: not established
                      - generic [ref=e423]:
                        - term [ref=e424]: "Validity:"
                        - definition [ref=e425]: not established
                      - generic [ref=e426]:
                        - term [ref=e427]: "Revalidation:"
                        - definition [ref=e428]: not required
                      - generic [ref=e429]:
                        - term [ref=e430]: "Cache age:"
                        - definition [ref=e431]: unknown (unrecognized)
                    - generic [ref=e432]:
                      - generic [ref=e433]:
                        - generic [ref=e434]:
                          - paragraph [ref=e435]: Trust framing
                          - heading "Authority caveats" [level=4] [ref=e436]:
                            - img [ref=e437]
                            - text: Authority caveats
                        - generic [ref=e439]: not_closeout_authority
                      - paragraph [ref=e440]: Use runtime scorecard/readiness authority before approval or closeout.
                      - paragraph [ref=e441]: Frontend signatures, badges, labels, and projections are not closeout authority.
                      - generic [ref=e442]:
                        - generic [ref=e443]: approval_authority
                        - generic [ref=e444]: readiness_authority
                        - generic [ref=e445]: runtime_closeout_authority
                        - generic [ref=e446]: scorecard_authority
                      - article [ref=e447]:
                        - generic [ref=e448]:
                          - paragraph [ref=e449]: Frontend integrity signature
                          - generic [ref=e450]: Integrity only
                        - paragraph [ref=e451]: This frontend signature verifies packet integrity only; it is not trust, approval, publication, or closeout authority.
                        - paragraph [ref=e452]: frontend_integrity_signature_not_authoritative
                    - generic [ref=e453]:
                      - generic [ref=e454]:
                        - generic [ref=e455]:
                          - generic [ref=e456]:
                            - paragraph [ref=e457]: E1 / Argument
                            - heading "Toulmin argument map" [level=4] [ref=e458]:
                              - img [ref=e459]
                              - text: Toulmin argument map
                          - generic [ref=e463]: "5"
                        - generic [ref=e464]:
                          - article [ref=e465]:
                            - generic [ref=e466]:
                              - paragraph [ref=e467]: "Public decision: owner verdict recorded"
                              - generic [ref=e468]: claim
                            - paragraph [ref=e469]: N/A
                            - paragraph [ref=e470]: claim / R_core_api_001
                          - article [ref=e471]:
                            - generic [ref=e472]:
                              - paragraph [ref=e473]: Published grounds
                              - generic [ref=e474]: grounds
                            - paragraph [ref=e475]: Applied Nodes is +1.00.
                            - paragraph [ref=e476]: grounds / metric:Applied_Nodes, metric:Policy_Cost
                          - article [ref=e477]:
                            - generic [ref=e478]:
                              - paragraph [ref=e479]: Policy warrant
                              - generic [ref=e480]: warrant
                            - paragraph [ref=e481]: The recommendation is warranted only when the published metrics, uncertainty, coverage and governance status remain aligned.
                            - paragraph [ref=e482]: warrant / atlas:publication:warrant
                          - article [ref=e483]:
                            - generic [ref=e484]:
                              - paragraph [ref=e485]: Evidence backing
                              - generic [ref=e486]: backing
                            - paragraph [ref=e487]: The public packet cites evidence artifacts without exposing private raw context.
                            - paragraph [ref=e488]: backing / sha256:7988bd2bd0a74ac54d450b2d6a7ace48fed1c287f08279c3bf9a7a93ff372045, sha256:d5cf87b14497b1e8a85bc20a3a98c698106e774312258b7a0ae08bd64e8dde67, sha256:326d60f1785dfdfacd7a4f57f0e0be1abb555c4817d072dcb123b32b9ff1ab3e
                          - article [ref=e489]:
                            - generic [ref=e490]:
                              - paragraph [ref=e491]: Governance issue references
                              - generic [ref=e492]: rebuttal
                            - paragraph [ref=e493]: 1 public governance issue reference(s) are attached.
                            - paragraph [ref=e494]: rebuttal / GOV001
                      - generic [ref=e495]:
                        - generic [ref=e496]:
                          - paragraph [ref=e497]: E5 / Confidence
                          - heading "Confidence ladder" [level=4] [ref=e498]:
                            - img [ref=e499]
                            - text: Confidence ladder
                        - article [ref=e503]:
                          - generic [ref=e504]:
                            - generic [ref=e505]:
                              - paragraph [ref=e506]: Owner confidence unavailable
                              - paragraph [ref=e507]: No owner-issued confidence quantity was supplied; absence remains unknown.
                            - button "Owner confidence quantity Unknown, untraced provenance available, Freshness Unknown" [ref=e509]:
                              - generic [ref=e510]: Unknown
                              - img [ref=e511]
                              - img [ref=e514]
                          - paragraph [ref=e517]: R_core_api_001
                    - generic [ref=e518]:
                      - generic [ref=e519]:
                        - paragraph [ref=e520]: E3 + E6 / Explanation
                        - heading "Deterministic explanations" [level=4] [ref=e521]:
                          - img [ref=e522]
                          - text: Deterministic explanations
                      - generic [ref=e524]:
                        - article [ref=e525]:
                          - paragraph [ref=e526]: Applied Nodes
                          - button "Applied Nodes 1, untraced provenance available, Freshness Unknown" [ref=e528]:
                            - generic [ref=e529]: "1"
                            - img [ref=e530]
                            - img [ref=e533]
                          - paragraph [ref=e536]: Applied Nodes is +1.00 because the public point estimate carries 70% of the explanation, uncertainty carries 10% (no public interval), and public provenance carries 20%.
                          - generic [ref=e537]:
                            - generic [ref=e538]:
                              - generic [ref=e539]: point estimate
                              - strong [ref=e540]: 70%
                            - generic [ref=e541]:
                              - generic [ref=e542]: uncertainty
                              - strong [ref=e543]: 10%
                            - generic [ref=e544]:
                              - generic [ref=e545]: public provenance
                              - strong [ref=e546]: 20%
                          - list [ref=e547]:
                            - listitem [ref=e548]: source / sha256:d5cf87b14497b1e8a85bc20a3a98c698106e774312258b7a0ae08bd64e8dde67
                            - listitem [ref=e549]: artifact / sha256:7988bd2bd0a74ac54d450b2d6a7ace48fed1c287f08279c3bf9a7a93ff372045
                            - listitem [ref=e550]: model / Applied Nodes
                            - listitem [ref=e551]: transform / publication narrative
                        - article [ref=e552]:
                          - paragraph [ref=e553]: Policy Cost
                          - button "Policy Cost 100, untraced provenance available, Freshness Unknown" [ref=e555]:
                            - generic [ref=e556]: "100"
                            - img [ref=e557]
                            - img [ref=e560]
                          - paragraph [ref=e563]: Policy Cost is +100.00 because the public point estimate carries 70% of the explanation, uncertainty carries 10% (no public interval), and public provenance carries 20%.
                          - generic [ref=e564]:
                            - generic [ref=e565]:
                              - generic [ref=e566]: point estimate
                              - strong [ref=e567]: 70%
                            - generic [ref=e568]:
                              - generic [ref=e569]: uncertainty
                              - strong [ref=e570]: 10%
                            - generic [ref=e571]:
                              - generic [ref=e572]: public provenance
                              - strong [ref=e573]: 20%
                          - list [ref=e574]:
                            - listitem [ref=e575]: source / sha256:d5cf87b14497b1e8a85bc20a3a98c698106e774312258b7a0ae08bd64e8dde67
                            - listitem [ref=e576]: artifact / sha256:7988bd2bd0a74ac54d450b2d6a7ace48fed1c287f08279c3bf9a7a93ff372045
                            - listitem [ref=e577]: model / Policy Cost
                            - listitem [ref=e578]: transform / publication narrative
                    - generic [ref=e579]:
                      - generic [ref=e580]:
                        - generic [ref=e581]:
                          - generic [ref=e582]:
                            - paragraph [ref=e583]: F1 / Model card
                            - heading "Citation-grade model card" [level=4] [ref=e584]:
                              - img [ref=e585]
                              - text: Citation-grade model card
                          - generic [ref=e588]: model:R_core_api_001
                        - generic [ref=e589]:
                          - article [ref=e590]:
                            - paragraph [ref=e591]: Intended use
                            - paragraph [ref=e592]: This card documents the public-facing model behavior used for the decision packet.
                            - paragraph [ref=e593]: R_core_api_001
                          - article [ref=e594]:
                            - paragraph [ref=e595]: Inputs and evidence
                            - paragraph [ref=e596]: "Published metrics: Applied Nodes, Policy Cost."
                            - paragraph [ref=e597]: model:R_core_api_001, sha256:7988bd2bd0a74ac54d450b2d6a7ace48fed1c287f08279c3bf9a7a93ff372045, sha256:d5cf87b14497b1e8a85bc20a3a98c698106e774312258b7a0ae08bd64e8dde67, sha256:326d60f1785dfdfacd7a4f57f0e0be1abb555c4817d072dcb123b32b9ff1ab3e
                          - article [ref=e598]:
                            - paragraph [ref=e599]: Validation
                            - paragraph [ref=e600]: The owner-recorded decision grade is reject; the recorded confidence label is unavailable.
                            - paragraph [ref=e601]: R_core_api_001
                          - article [ref=e602]:
                            - paragraph [ref=e603]: Limitations
                            - paragraph [ref=e604]: Restricted notes, raw values and embargoed evidence are excluded from this public card.
                            - paragraph [ref=e605]: atlas:public-redaction
                      - generic [ref=e606]:
                        - generic [ref=e607]:
                          - generic [ref=e608]:
                            - paragraph [ref=e609]: F3 / Coverage
                            - heading "Coverage caveat" [level=4] [ref=e610]:
                              - img [ref=e611]
                              - text: Coverage caveat
                          - generic [ref=e615]: clear
                        - paragraph [ref=e616]: No calculated coverage display is in the low band; owner publication semantics are not inferred.
                        - article [ref=e618]:
                          - generic [ref=e619]:
                            - paragraph [ref=e620]: USA
                            - generic [ref=e621]: "0.64"
                          - paragraph [ref=e622]: Calculated coverage falls in the middle display band; inspect the source references.
                      - generic [ref=e623]:
                        - generic [ref=e624]:
                          - generic [ref=e625]:
                            - paragraph [ref=e626]: F4 / Threshold
                            - heading "Threshold microcontract" [level=4] [ref=e627]:
                              - img [ref=e628]
                              - text: Threshold microcontract
                          - generic [ref=e632]: Unknown
                        - paragraph [ref=e633]: Decision threshold proximity is unavailable until a producer threshold contract is supplied.
                        - generic [ref=e635]: Unknown
                      - generic [ref=e636]:
                        - generic [ref=e637]:
                          - paragraph [ref=e638]: F5 / Forms
                          - heading "Locale-aware bureaucratic forms" [level=4] [ref=e639]:
                            - img [ref=e640]
                            - text: Locale-aware bureaucratic forms
                        - generic [ref=e643]:
                          - article [ref=e644]:
                            - generic [ref=e645]:
                              - paragraph [ref=e646]: Наказ
                              - generic [ref=e647]: uk-UA
                            - paragraph [ref=e648]: requisites -> preamble -> order -> control -> signature
                            - paragraph [ref=e649]: bureaucratic_ast_patch.v1
                          - article [ref=e650]:
                            - generic [ref=e651]:
                              - paragraph [ref=e652]: Розпорядження
                              - generic [ref=e653]: uk-UA
                            - paragraph [ref=e654]: requisites -> legal_basis -> directive -> execution -> signature
                            - paragraph [ref=e655]: bureaucratic_ast_patch.v1
                          - article [ref=e656]:
                            - generic [ref=e657]:
                              - paragraph [ref=e658]: Постанова
                              - generic [ref=e659]: uk-UA
                            - paragraph [ref=e660]: requisites -> preamble -> operative_part -> annexes -> signature
                            - paragraph [ref=e661]: bureaucratic_ast_patch.v1
                          - article [ref=e662]:
                            - generic [ref=e663]:
                              - paragraph [ref=e664]: Висновок
                              - generic [ref=e665]: uk-UA
                            - paragraph [ref=e666]: requisites -> question -> analysis -> evidence -> conclusion -> signature
                            - paragraph [ref=e667]: bureaucratic_ast_patch.v1
                    - generic [ref=e668]:
                      - generic [ref=e669]:
                        - paragraph [ref=e670]: E4 / Glossary
                        - heading "Glossary lens" [level=4] [ref=e671]
                      - generic [ref=e672]:
                        - article [ref=e673]:
                          - paragraph [ref=e674]: decision packet
                          - paragraph [ref=e675]: A decision-bearing record that keeps outcome, evidence, uncertainty, provenance and review status together.
                          - paragraph [ref=e676]: Atlas design system / Apr 29, 2026, 3:00 AM / docs/brand/ATLAS_DESIGN_SYSTEM.md#decision-packet
                        - article [ref=e677]:
                          - paragraph [ref=e678]: provenance
                          - paragraph [ref=e679]: A trace from source data through transformations, model output and artifact publication.
                          - paragraph [ref=e680]: Evidence Fabric / Apr 29, 2026, 3:00 AM / docs/brand/ATLAS_DESIGN_SYSTEM.md#provenance
                        - article [ref=e681]:
                          - paragraph [ref=e682]: uncertainty
                          - paragraph [ref=e683]: A confidence, interval or identifiability marker that changes how strongly a claim can be used.
                          - paragraph [ref=e684]: Scientist layer / Apr 29, 2026, 3:00 AM / docs/brand/ATLAS_DESIGN_SYSTEM.md#uncertainty
                        - article [ref=e685]:
                          - paragraph [ref=e686]: threshold microcontract
                          - paragraph [ref=e687]: A policy cutoff contract that exposes the threshold, edge cases and calibration caveat.
                          - paragraph [ref=e688]: PolicyOS governance / Apr 29, 2026, 3:00 AM / docs/plans/active/DESIGN_BEST_IN_CLASS_PLAN.md#f4
                        - article [ref=e689]:
                          - paragraph [ref=e690]: coverage caveat
                          - paragraph [ref=e691]: A public warning attached when affected geography or cohort evidence is sparse.
                          - paragraph [ref=e692]: Evidence Fabric / Apr 29, 2026, 3:00 AM / docs/plans/active/DESIGN_BEST_IN_CLASS_PLAN.md#f3
                  - generic [ref=e693]:
                    - generic [ref=e694]:
                      - generic [ref=e695]:
                        - paragraph [ref=e696]: Phase 3.6 / Operator craft
                        - heading "Reviewer craft layer" [level=3] [ref=e697]
                        - paragraph [ref=e698]: The reviewer can set a global trust threshold, annotate the exact packet snapshot, save evidence to a personal wallet, and complete a reading-grade first run.
                      - generic [ref=e699]: 1/8 complete
                    - generic [ref=e700]:
                      - generic [ref=e701]:
                        - generic [ref=e702]:
                          - generic [ref=e703]:
                            - paragraph [ref=e704]: G1 / Trust
                            - heading "Global trust threshold" [level=4] [ref=e705]
                          - img [ref=e707]
                        - generic [ref=e708]:
                          - generic [ref=e709]:
                            - generic [ref=e710]: Current threshold
                            - strong [ref=e711]: 60%
                          - generic "Global trust threshold" [ref=e712]:
                            - slider "Global trust threshold" [ref=e716]
                          - generic [ref=e717]:
                            - generic [ref=e718]:
                              - generic [ref=e719]: visible claims
                              - strong [ref=e720]: "1"
                            - generic [ref=e721]:
                              - generic [ref=e722]: hidden claims
                              - strong [ref=e723]: "0"
                            - generic [ref=e724]:
                              - generic [ref=e725]: remaining
                              - strong [ref=e726]: 100%
                          - paragraph [ref=e728]: No claims are hidden at this threshold.
                          - paragraph [ref=e729]: Updated Jan 1, 1970, 3:00 AM
                      - generic [ref=e730]:
                        - generic [ref=e731]:
                          - generic [ref=e732]:
                            - paragraph [ref=e733]: G2 / Annotation
                            - heading "Snapshot annotations" [level=4] [ref=e734]
                          - img [ref=e736]
                        - generic [ref=e738]:
                          - generic [ref=e739]:
                            - generic [ref=e740]: Target
                            - combobox "Target" [ref=e741]:
                              - 'option "Public decision: owner verdict recorded" [selected]'
                              - 'option "Public decision: owner verdict recorded"'
                              - option "Published grounds"
                              - option "Policy warrant"
                              - option "Evidence backing"
                              - option "Applied Nodes"
                              - option "Policy Cost"
                              - option "No calculated coverage display is in the low band; owner publication semantics are not inferred."
                              - option "policy:R_core_api_001"
                              - option "Citation-grade model card"
                          - textbox "Write an audit note tied to this packet hash." [ref=e742]
                          - button "Add annotation" [disabled]:
                            - img
                            - generic: Add annotation
                        - paragraph [ref=e744]: No snapshot annotations yet.
                    - generic [ref=e745]:
                      - generic [ref=e746]:
                        - generic [ref=e747]:
                          - generic [ref=e748]:
                            - paragraph [ref=e749]: G3 / Evidence
                            - heading "Evidence wallet" [level=4] [ref=e750]
                          - img [ref=e752]
                        - generic [ref=e756]:
                          - article [ref=e757]:
                            - generic [ref=e758]:
                              - generic [ref=e759]:
                                - strong [ref=e760]: PolicyOS decision model
                                - paragraph [ref=e761]: model reference from citation-grade model card.
                              - button "Save" [ref=e762]:
                                - img [ref=e763]
                                - generic [ref=e765]: Save
                          - article [ref=e766]:
                            - generic [ref=e767]:
                              - generic [ref=e768]:
                                - strong [ref=e769]: fabric.evidence_bundle
                                - paragraph [ref=e770]: artifact reference from citation-grade model card.
                              - button "Save" [ref=e771]:
                                - img [ref=e772]
                                - generic [ref=e774]: Save
                          - article [ref=e775]:
                            - generic [ref=e776]:
                              - generic [ref=e777]:
                                - strong [ref=e778]: fabric.data_snapshot
                                - paragraph [ref=e779]: artifact reference from citation-grade model card.
                              - button "Save" [ref=e780]:
                                - img [ref=e781]
                                - generic [ref=e783]: Save
                          - article [ref=e784]:
                            - generic [ref=e785]:
                              - generic [ref=e786]:
                                - strong [ref=e787]: foundry.input_bindings
                                - paragraph [ref=e788]: artifact reference from citation-grade model card.
                              - button "Save" [ref=e789]:
                                - img [ref=e790]
                                - generic [ref=e792]: Save
                          - article [ref=e793]:
                            - generic [ref=e794]:
                              - generic [ref=e795]:
                                - strong [ref=e796]: Applied Nodes
                                - paragraph [ref=e797]: Applied Nodes is +1.00 because the public point estimate carries 70% of the explanation, uncertainty carries 10% (no public interval), and public provenance carries 20%.
                              - button "Save" [ref=e798]:
                                - img [ref=e799]
                                - generic [ref=e801]: Save
                        - generic [ref=e802]:
                          - paragraph [ref=e803]: Saved evidence
                          - paragraph [ref=e804]: No evidence has been saved for this packet.
                      - generic [ref=e805]:
                        - generic [ref=e806]:
                          - generic [ref=e807]:
                            - paragraph [ref=e808]: G5 / Onboarding
                            - heading "Reading-grade onboarding" [level=4] [ref=e809]
                          - img [ref=e811]
                        - generic [ref=e814]:
                          - generic [ref=e817]:
                            - generic [ref=e818]: 1/8 complete
                            - button "Start run" [ref=e819]:
                              - img [ref=e820]
                              - generic [ref=e823]: Start run
                          - generic [ref=e824]:
                            - generic [ref=e825]:
                              - generic [ref=e826]:
                                - strong [ref=e827]: Read the decision packet
                                - generic [ref=e828]: decision.summary
                              - generic [ref=e829]:
                                - generic [ref=e830]: Pending
                                - button "Complete" [ref=e831]:
                                  - generic [ref=e832]: Complete
                            - generic [ref=e833]:
                              - generic [ref=e834]:
                                - strong [ref=e835]: Inspect the argument map
                                - generic [ref=e836]: argument.map
                              - generic [ref=e837]:
                                - generic [ref=e838]: Pending
                                - button "Complete" [ref=e839]:
                                  - generic [ref=e840]: Complete
                            - generic [ref=e841]:
                              - generic [ref=e842]:
                                - strong [ref=e843]: Narrate provenance
                                - generic [ref=e844]: derivation.path
                              - generic [ref=e845]:
                                - generic [ref=e846]: Pending
                                - button "Complete" [ref=e847]:
                                  - generic [ref=e848]: Complete
                            - generic [ref=e849]:
                              - generic [ref=e850]:
                                - strong [ref=e851]: Open glossary lens
                                - generic [ref=e852]: glossary.lens
                              - generic [ref=e853]:
                                - generic [ref=e854]: Pending
                                - button "Complete" [ref=e855]:
                                  - generic [ref=e856]: Complete
                            - generic [ref=e857]:
                              - generic [ref=e858]:
                                - strong [ref=e859]: Set global threshold
                                - generic [ref=e860]: threshold.profile
                              - generic [ref=e861]:
                                - generic [ref=e862]: Pending
                                - button "Complete" [ref=e863]:
                                  - generic [ref=e864]: Complete
                            - generic [ref=e865]:
                              - generic [ref=e866]:
                                - strong [ref=e867]: Save evidence to wallet
                                - generic [ref=e868]: evidence.wallet
                              - generic [ref=e869]:
                                - generic [ref=e870]: Pending
                                - button "Complete" [ref=e871]:
                                  - generic [ref=e872]: Complete
                            - generic [ref=e873]:
                              - generic [ref=e874]:
                                - strong [ref=e875]: Annotate packet snapshot
                                - generic [ref=e876]: annotation.snapshot
                              - generic [ref=e878]: done
                            - generic [ref=e879]:
                              - generic [ref=e880]:
                                - strong [ref=e881]: Complete
                                - generic [ref=e882]: onboarding.checklist_complete
                              - generic [ref=e883]:
                                - generic [ref=e884]: Pending
                                - button "Complete" [disabled]:
                                  - generic: Complete
                - navigation "Run workspace sections" [ref=e885]:
                  - generic [ref=e886]:
                    - link "overview" [ref=e887] [cursor=pointer]:
                      - /url: /runs/R_core_api_001/overview
                    - link "pages.runs.tabs.causal" [ref=e888] [cursor=pointer]:
                      - /url: /runs/R_core_api_001/causal
                    - link "governance" [ref=e889] [cursor=pointer]:
                      - /url: /runs/R_core_api_001/governance
                    - link "evidence" [ref=e890] [cursor=pointer]:
                      - /url: /runs/R_core_api_001/evidence
                    - link "workflow" [ref=e891] [cursor=pointer]:
                      - /url: /runs/R_core_api_001/workflow
                    - link "artifacts" [ref=e892] [cursor=pointer]:
                      - /url: /runs/R_core_api_001/artifacts
                    - link "agents" [ref=e893] [cursor=pointer]:
                      - /url: /runs/R_core_api_001/agents
                    - link "debug" [ref=e894] [cursor=pointer]:
                      - /url: /runs/R_core_api_001/debug
                - generic [ref=e895]:
                  - generic [ref=e896]:
                    - generic [ref=e897]:
                      - generic [ref=e899]:
                        - paragraph [ref=e900]: Decision
                        - heading "reject" [level=4] [ref=e901]
                      - generic [ref=e902]:
                        - link "Reading view" [ref=e904] [cursor=pointer]:
                          - /url: /artifacts/sha256:9836fd27dedc46ca60fa8a3939d39d8d4e5c99280149a8e16ada1791a7a2bc62?tab=content&view=reading
                        - paragraph [ref=e905]:
                          - generic [ref=e906]: AI-generated by Drafter.
                          - generic [ref=e907]: ⊙
                          - text: N/A
                        - generic [ref=e908]:
                          - article [ref=e909]:
                            - generic [ref=e911]: Evaluator
                            - strong [ref=e912]: REPLAN_DATA
                          - article [ref=e913]:
                            - generic [ref=e915]: score 0.67
                            - strong [ref=e916]:
                              - button "Run decision score 67%, untraced provenance available, Freshness Unknown" [ref=e917]:
                                - generic [ref=e918]: 67%
                                - img [ref=e919]
                                - img [ref=e922]
                    - generic [ref=e925]:
                      - generic [ref=e927]:
                        - paragraph [ref=e928]: Governance
                        - heading "blockers 1" [level=4] [ref=e929]
                      - generic [ref=e930]:
                        - article [ref=e931]:
                          - generic [ref=e933]: Governance
                          - strong [ref=e934]:
                            - button "Governance 1 blockers, untraced provenance available, Freshness Unknown" [ref=e935]:
                              - generic [ref=e936]: "1"
                              - generic [ref=e937]: blockers
                              - img [ref=e938]
                              - img [ref=e941]
                        - article [ref=e944]:
                          - generic [ref=e946]: Transport
                          - strong [ref=e947]: blocked
                      - generic [ref=e949]:
                        - generic [ref=e950]:
                          - strong [ref=e951]: Policy blocker
                          - generic [ref=e952]: blocker
                        - paragraph [ref=e953]: GOV001
                  - generic [ref=e954]:
                    - generic [ref=e955]:
                      - generic [ref=e956]:
                        - generic [ref=e957]:
                          - paragraph [ref=e958]: Evidence
                          - 'heading "Plans: 1 · Promotions: 1" [level=4] [ref=e959]'
                        - link "evidence" [ref=e960] [cursor=pointer]:
                          - /url: /runs/R_core_api_001/evidence
                      - generic [ref=e961]:
                        - article [ref=e962]:
                          - generic [ref=e964]: Data needs
                          - strong [ref=e965]: "1"
                        - article [ref=e966]:
                          - generic [ref=e968]: Fetch plans
                          - strong [ref=e969]: "1"
                        - article [ref=e970]:
                          - generic [ref=e972]: Promotion candidates
                          - strong [ref=e973]: "1"
                      - generic [ref=e974]:
                        - generic [ref=e975]:
                          - strong [ref=e976]: macro.gdp.real
                          - paragraph [ref=e977]: USA · 2019 - 2024
                        - generic [ref=e978]:
                          - strong [ref=e979]: worldbank.wdi / NY.GDP.MKTP.KD
                          - paragraph [ref=e980]: macro.gdp.real
                        - generic [ref=e981]:
                          - strong [ref=e982]: macro.gdp.real
                          - paragraph [ref=e983]: lane ExploreLane · confidence 87% · status pending
                    - generic [ref=e984]:
                      - generic [ref=e986]:
                        - paragraph [ref=e987]: Events
                        - heading "Latest timeline events" [level=4] [ref=e988]
                      - generic [ref=e989]:
                        - generic [ref=e990]:
                          - generic [ref=e991]:
                            - strong [ref=e992]: RUN_STARTED
                            - generic [ref=e993]: Sep 1, 2026, 9:54 PM
                          - paragraph [ref=e994]: core
                        - generic [ref=e995]:
                          - generic [ref=e996]:
                            - strong [ref=e997]: RUN_INPUT_ADDED
                            - generic [ref=e998]: Sep 1, 2026, 9:54 PM
                          - paragraph [ref=e999]: core
                        - generic [ref=e1000]:
                          - generic [ref=e1001]:
                            - strong [ref=e1002]: RUN_INPUT_ADDED
                            - generic [ref=e1003]: Sep 1, 2026, 9:54 PM
                          - paragraph [ref=e1004]: core
                        - generic [ref=e1005]:
                          - generic [ref=e1006]:
                            - strong [ref=e1007]: RUN_INPUT_ADDED
                            - generic [ref=e1008]: Sep 1, 2026, 9:54 PM
                          - paragraph [ref=e1009]: core
                        - generic [ref=e1010]:
                          - generic [ref=e1011]:
                            - strong [ref=e1012]: RUN_INPUT_ADDED
                            - generic [ref=e1013]: Sep 1, 2026, 9:54 PM
                          - paragraph [ref=e1014]: core
                  - generic [ref=e1016]:
                    - generic [ref=e1017]:
                      - generic [ref=e1018]:
                        - heading "Scenario workbench" [level=2] [ref=e1019]
                        - paragraph [ref=e1020]: Compare actual runtime values with a named scenario manifest.
                      - radiogroup "Counterfactual mode" [ref=e1021]:
                        - radio "Actual" [checked] [ref=e1022]
                        - radio "Actual + Scenario" [ref=e1023]
                        - radio "Scenario" [ref=e1024]
                    - generic [ref=e1025]:
                      - generic [ref=e1026]:
                        - generic [ref=e1027]:
                          - generic [ref=e1028]:
                            - generic [ref=e1029]: Scenario
                            - generic [ref=e1030]:
                              - img [ref=e1031]
                              - text: Computed
                          - combobox "Scenario" [ref=e1038]:
                            - option "Choose scenario"
                            - option "What if the primary policy lever moved within safe bounds? · Computed" [selected]
                        - region "Scenario manifest" [ref=e1039]:
                          - generic [ref=e1040]:
                            - generic [ref=e1041]:
                              - heading "What if the primary policy lever moved within safe bounds?" [level=3] [ref=e1042]
                              - paragraph [ref=e1043]: Baseline run R_core_api_001
                            - generic [ref=e1044]:
                              - img [ref=e1045]
                              - text: Computed
                          - generic [ref=e1052]:
                            - generic [ref=e1053]:
                              - term [ref=e1054]:
                                - img [ref=e1055]
                                - text: Author
                              - definition [ref=e1058]: PolicyOS scenario generator
                            - generic [ref=e1059]:
                              - term [ref=e1060]:
                                - img [ref=e1061]
                                - text: Model
                              - definition [ref=e1065]: runtime-counterfactual-linearized
                            - generic [ref=e1066]:
                              - term [ref=e1067]:
                                - img [ref=e1068]
                                - text: Computed
                              - definition [ref=e1071]: Sep 1, 2026, 9:54 PM
                          - generic [ref=e1072]:
                            - paragraph [ref=e1073]: Assumptions
                            - generic [ref=e1075]:
                              - img [ref=e1076]
                              - generic [ref=e1079]: No external demand shock
                              - generic [ref=e1080]: operator
                          - generic [ref=e1081]:
                            - paragraph [ref=e1082]: Known limitations
                            - list [ref=e1083]:
                              - listitem [ref=e1084]: Foundation scenario uses a bounded deterministic sensitivity transform.
                              - listitem [ref=e1085]: Promotion to verified scenario requires model execution and review.
                        - generic [ref=e1086]:
                          - paragraph [ref=e1087]: policy_cost intervention
                          - generic [ref=e1088]:
                            - generic [ref=e1089]:
                              - text: Baseline value
                              - textbox "Baseline value" [ref=e1090]: "100"
                            - generic [ref=e1091]:
                              - text: Scenario value
                              - spinbutton "Scenario value" [ref=e1092]: "90"
                          - paragraph [ref=e1093]: 1 constraint applies
                        - generic [ref=e1094]:
                          - heading "Scenario validation" [level=3] [ref=e1095]
                          - paragraph [ref=e1096]: computed
                          - list [ref=e1097]:
                            - listitem [ref=e1098]: Foundation scenario uses a bounded deterministic sensitivity transform.
                            - listitem [ref=e1099]: Promotion to verified scenario requires model execution and review.
                      - generic [ref=e1100]:
                        - heading "Scenario metrics" [level=3] [ref=e1101]
                        - generic [ref=e1102]:
                          - generic [ref=e1103]:
                            - 'figure "applied_nodes: baseline, scenario and difference chart for scn_R_core_api_001_bounded_shift" [ref=e1104]':
                              - generic [ref=e1105]:
                                - generic [ref=e1106]:
                                  - generic [ref=e1107]: Actual
                                  - generic "applied_nodes 1 count, verified provenance available" [ref=e1111]:
                                    - generic [ref=e1112]: "1"
                                    - generic [ref=e1113]: count
                                    - img [ref=e1114]
                                - generic [ref=e1117]:
                                  - generic [ref=e1118]: Scenario
                                  - generic "applied_nodes scenario value 1.05 count, pending provenance available" [ref=e1122]:
                                    - generic [ref=e1123]: "1.05"
                                    - generic [ref=e1124]: count
                                    - img [ref=e1125]
                                - generic [ref=e1128]:
                                  - generic [ref=e1129]: Delta
                                  - generic "applied_nodes scenario delta 0.05 count, pending provenance available" [ref=e1133]:
                                    - generic [ref=e1134]: "0.05"
                                    - generic [ref=e1135]: count
                                    - img [ref=e1136]
                              - generic [ref=e1140]:
                                - img [ref=e1141]
                                - generic [ref=e1144]: No external demand shock
                                - generic [ref=e1145]: operator
                            - 'generic "applied_nodes: actual and scenario values for scn_R_core_api_001_bounded_shift" [ref=e1146]':
                              - generic [ref=e1147]:
                                - generic [ref=e1148]: Actual
                                - button "applied_nodes baseline value" [ref=e1149]:
                                  - generic [ref=e1150]: "1"
                                  - generic [ref=e1151]: count
                                  - img [ref=e1152]
                              - generic [ref=e1155]:
                                - generic [ref=e1156]: Scenario
                                - button "applied_nodes scenario value in scn_R_core_api_001_bounded_shift" [ref=e1157]:
                                  - generic [ref=e1158]: "1.05"
                                  - generic [ref=e1159]: count
                                  - img [ref=e1160]
                              - generic [ref=e1163]:
                                - generic [ref=e1164]: Delta
                                - generic "Scenario difference 0.050000000000000044" [ref=e1165]:
                                  - img [ref=e1166]
                                  - button "applied_nodes scenario delta 0.05 count, pending provenance available" [ref=e1169]:
                                    - generic [ref=e1170]: "0.05"
                                    - generic [ref=e1171]: count
                                    - img [ref=e1172]
                              - generic [ref=e1175]:
                                - img [ref=e1176]
                                - text: Computed
                          - generic [ref=e1183]:
                            - 'figure "policy_cost: baseline, scenario and difference chart for scn_R_core_api_001_bounded_shift" [ref=e1184]':
                              - generic [ref=e1185]:
                                - generic [ref=e1186]:
                                  - generic [ref=e1187]: Actual
                                  - generic "policy_cost 100 USD, verified provenance available" [ref=e1191]:
                                    - generic [ref=e1192]: "100"
                                    - generic [ref=e1193]: USD
                                    - img [ref=e1194]
                                - generic [ref=e1197]:
                                  - generic [ref=e1198]: Scenario
                                  - generic "policy_cost scenario value 90 USD, pending provenance available" [ref=e1202]:
                                    - generic [ref=e1203]: "90"
                                    - generic [ref=e1204]: USD
                                    - img [ref=e1205]
                                - generic [ref=e1208]:
                                  - generic [ref=e1209]: Delta
                                  - generic "policy_cost scenario delta -10 USD, pending provenance available" [ref=e1213]:
                                    - generic [ref=e1214]: "-10"
                                    - generic [ref=e1215]: USD
                                    - img [ref=e1216]
                              - generic [ref=e1220]:
                                - img [ref=e1221]
                                - generic [ref=e1224]: No external demand shock
                                - generic [ref=e1225]: operator
                            - 'generic "policy_cost: actual and scenario values for scn_R_core_api_001_bounded_shift" [ref=e1226]':
                              - generic [ref=e1227]:
                                - generic [ref=e1228]: Actual
                                - button "policy_cost baseline value" [ref=e1229]:
                                  - generic [ref=e1230]: "100"
                                  - generic [ref=e1231]: USD
                                  - img [ref=e1232]
                              - generic [ref=e1235]:
                                - generic [ref=e1236]: Scenario
                                - button "policy_cost scenario value in scn_R_core_api_001_bounded_shift" [ref=e1237]:
                                  - generic [ref=e1238]: "90"
                                  - generic [ref=e1239]: USD
                                  - img [ref=e1240]
                              - generic [ref=e1243]:
                                - generic [ref=e1244]: Delta
                                - generic "Scenario difference -10" [ref=e1245]:
                                  - img [ref=e1246]
                                  - button "policy_cost scenario delta -10 USD, pending provenance available" [ref=e1249]:
                                    - generic [ref=e1250]: "-10"
                                    - generic [ref=e1251]: USD
                                    - img [ref=e1252]
                              - generic [ref=e1255]:
                                - img [ref=e1256]
                                - text: Computed
                          - generic [ref=e1263]:
                            - 'figure "Backtest trust score: baseline, scenario and difference chart for scn_R_core_api_001_bounded_shift" [ref=e1264]':
                              - generic [ref=e1265]:
                                - generic [ref=e1266]:
                                  - generic [ref=e1267]: Actual
                                  - generic "Backtest trust score 0.82 score, verified provenance available" [ref=e1271]:
                                    - generic [ref=e1272]: "0.82"
                                    - generic [ref=e1273]: score
                                    - img [ref=e1274]
                                - generic [ref=e1277]:
                                  - generic [ref=e1278]: Scenario
                                  - generic "Backtest trust score scenario value 0.861 score, pending provenance available" [ref=e1282]:
                                    - generic [ref=e1283]: "0.861"
                                    - generic [ref=e1284]: score
                                    - img [ref=e1285]
                                - generic [ref=e1288]:
                                  - generic [ref=e1289]: Delta
                                  - generic "Backtest trust score scenario delta 0.041 score, pending provenance available" [ref=e1293]:
                                    - generic [ref=e1294]: "0.041"
                                    - generic [ref=e1295]: score
                                    - img [ref=e1296]
                              - generic [ref=e1300]:
                                - img [ref=e1301]
                                - generic [ref=e1304]: No external demand shock
                                - generic [ref=e1305]: operator
                            - 'generic "Backtest trust score: actual and scenario values for scn_R_core_api_001_bounded_shift" [ref=e1306]':
                              - generic [ref=e1307]:
                                - generic [ref=e1308]: Actual
                                - button "Backtest trust score baseline value" [ref=e1309]:
                                  - generic [ref=e1310]: "0.82"
                                  - generic [ref=e1311]: score
                                  - img [ref=e1312]
                              - generic [ref=e1315]:
                                - generic [ref=e1316]: Scenario
                                - button "Backtest trust score scenario value in scn_R_core_api_001_bounded_shift" [ref=e1317]:
                                  - generic [ref=e1318]: "0.861"
                                  - generic [ref=e1319]: score
                                  - img [ref=e1320]
                              - generic [ref=e1323]:
                                - generic [ref=e1324]: Delta
                                - generic "Scenario difference 0.041000000000000036" [ref=e1325]:
                                  - img [ref=e1326]
                                  - button "Backtest trust score scenario delta 0.041 score, pending provenance available" [ref=e1329]:
                                    - generic [ref=e1330]: "0.041"
                                    - generic [ref=e1331]: score
                                    - img [ref=e1332]
                              - generic [ref=e1335]:
                                - img [ref=e1336]
                                - text: Computed
                  - generic [ref=e1343]:
                    - generic [ref=e1344]:
                      - generic [ref=e1345]:
                        - paragraph [ref=e1346]: Explainability
                        - heading "Decision transparency and trust signals" [level=4] [ref=e1347]
                      - link "Open Cycle Board global cohort — not this run" [ref=e1348] [cursor=pointer]:
                        - /url: /runs/cycle-board
                    - generic [ref=e1349]:
                      - button "Run decision score 0.67 ratio, untraced provenance available, Freshness Unknown" [ref=e1351]:
                        - generic [ref=e1352]: "0.67"
                        - generic [ref=e1353]: ratio
                        - img [ref=e1354]
                        - img [ref=e1357]
                      - generic [ref=e1360]:
                        - generic [ref=e1361]:
                          - paragraph [ref=e1362]: Provenance chain
                          - generic [ref=e1363]:
                            - heading "Provenance" [level=3] [ref=e1364]
                            - generic [ref=e1365]:
                              - generic [ref=e1366]:
                                - img [ref=e1369]
                                - generic [ref=e1374]:
                                  - generic [ref=e1375]:
                                    - paragraph [ref=e1376]: Evidence needs identified
                                    - generic [ref=e1377]: dataset
                                  - paragraph [ref=e1378]: 1 evidence needs mapped to the run.
                              - generic [ref=e1379]:
                                - img [ref=e1382]
                                - generic [ref=e1387]:
                                  - generic [ref=e1388]:
                                    - paragraph [ref=e1389]: Evidence collection planned
                                    - generic [ref=e1390]: method
                                  - paragraph [ref=e1391]: 1 fetch plans prepared for supporting evidence.
                              - generic [ref=e1392]:
                                - img [ref=e1395]
                                - generic [ref=e1400]:
                                  - generic [ref=e1401]:
                                    - paragraph [ref=e1402]: Analysis executed
                                    - generic [ref=e1403]: fail
                                    - generic [ref=e1404]: result
                                  - paragraph [ref=e1405]: fail
                                  - generic [ref=e1407]: 2026-09-01T18:54:11Z
                              - generic [ref=e1408]:
                                - img [ref=e1411]
                                - generic [ref=e1415]:
                                  - generic [ref=e1416]:
                                    - paragraph [ref=e1417]: Governance review
                                    - generic [ref=e1418]: artifact
                                  - paragraph [ref=e1419]: 1 blockers, 0 warnings.
                        - generic [ref=e1420]:
                          - paragraph [ref=e1421]: Governance passes
                          - generic [ref=e1422]:
                            - generic [ref=e1423]:
                              - heading "Governance passes" [level=3] [ref=e1424]
                              - generic [ref=e1425]: 3 diagnostics
                            - paragraph [ref=e1426]: error · REPLAN_DATA · unknown
                            - generic [ref=e1427]:
                              - 'button "Preflight: error" [ref=e1428]':
                                - img [ref=e1429]
                              - 'button "Evaluator: REPLAN_DATA" [ref=e1432]':
                                - img [ref=e1433]
                              - 'button "Reproducibility: unknown" [ref=e1436]':
                                - img [ref=e1437]
                        - generic [ref=e1440]:
                          - paragraph [ref=e1441]: Attribution
                          - generic [ref=e1442]:
                            - heading "Attribution waterfall" [level=3] [ref=e1443]
                            - img "Waterfall chart. 4 steps from Base prediction to Final estimate." [ref=e1444]:
                              - img [ref=e1445]:
                                - generic [ref=e1446]:
                                  - generic [ref=e1448]: "0.00"
                                  - generic [ref=e1449]: Base pred…
                                - generic [ref=e1450]:
                                  - generic [ref=e1452]: "+1.00"
                                  - generic [ref=e1453]: Applied N…
                                - generic [ref=e1454]:
                                  - generic [ref=e1456]: "+100.00"
                                  - generic [ref=e1457]: Policy Co…
                                - generic [ref=e1458]:
                                  - generic [ref=e1460]: "101.00"
                                  - generic [ref=e1461]: Final est…
                              - table "Waterfall chart data" [ref=e1462]:
                                - caption [ref=e1463]: Waterfall chart data
                                - rowgroup [ref=e1464]:
                                  - row "Label Value Cumulative" [ref=e1465]:
                                    - columnheader "Label" [ref=e1466]
                                    - columnheader "Value" [ref=e1467]
                                    - columnheader "Cumulative" [ref=e1468]
                                - rowgroup [ref=e1469]:
                                  - row "Base prediction 0.000 0.000" [ref=e1470]:
                                    - rowheader "Base prediction" [ref=e1471]
                                    - cell "0.000" [ref=e1472]
                                    - cell "0.000" [ref=e1473]
                                  - row "Applied Nodes 1.000 1.000" [ref=e1474]:
                                    - rowheader "Applied Nodes" [ref=e1475]
                                    - cell "1.000" [ref=e1476]
                                    - cell "1.000" [ref=e1477]
                                  - row "Policy Cost 100.000 101.000" [ref=e1478]:
                                    - rowheader "Policy Cost" [ref=e1479]
                                    - cell "100.000" [ref=e1480]
                                    - cell "101.000" [ref=e1481]
                                  - row "Final estimate 101.000 101.000" [ref=e1482]:
                                    - rowheader "Final estimate" [ref=e1483]
                                    - cell "101.000" [ref=e1484]
                                    - cell "101.000" [ref=e1485]
                            - table [ref=e1487]:
                              - rowgroup [ref=e1488]:
                                - row "Factor Contribution Detail" [ref=e1489]:
                                  - columnheader "Factor" [ref=e1490]
                                  - columnheader "Contribution" [ref=e1491]
                                  - columnheader "Detail" [ref=e1492]
                              - rowgroup [ref=e1493]:
                                - row "Base prediction Attribution baseline 0, untraced provenance available, Freshness Unknown" [ref=e1494]:
                                  - cell "Base prediction" [ref=e1495]
                                  - cell "Attribution baseline 0, untraced provenance available, Freshness Unknown" [ref=e1496]:
                                    - button "Attribution baseline 0, untraced provenance available, Freshness Unknown" [ref=e1498]:
                                      - generic [ref=e1499]: "0"
                                      - img [ref=e1500]
                                      - img [ref=e1503]
                                  - cell [ref=e1506]
                                - row "Policy Cost +100.0000 +100.00" [ref=e1507]:
                                  - cell "Policy Cost" [ref=e1508]
                                  - cell "+100.0000" [ref=e1509]
                                  - cell "+100.00" [ref=e1510]
                                - row "Applied Nodes +1.0000 +1.00" [ref=e1511]:
                                  - cell "Applied Nodes" [ref=e1512]
                                  - cell "+1.0000" [ref=e1513]
                                  - cell "+1.00" [ref=e1514]
                                - row "Final estimate 101.0000" [ref=e1515]:
                                  - cell "Final estimate" [ref=e1516]
                                  - cell "101.0000" [ref=e1517]
                                  - cell [ref=e1518]
  - region "Notifications"
  - status [ref=e1519]
  - alert [ref=e1520]
```

# Test source

```ts
  1149 |     await expect(
  1150 |       story.getByTestId("authority-badge-fixture-rejection"),
  1151 |     ).toHaveAttribute("data-fixture-rejection", /fixture provenance/i);
  1152 |     await expect(story.locator("[data-authority-recognition]")).toHaveCount(0);
  1153 |     await expect(story).toHaveScreenshot("ds4-fixture-only-boundary.png", {
  1154 |       animations: "disabled",
  1155 |       caret: "hide",
  1156 |     });
  1157 |   });
  1158 | 
  1159 |   test("renders every DS4 evidence primitive", async ({ page }) => {
  1160 |     const story = await openEvidencePrimitiveStory(
  1161 |       page,
  1162 |       "ds4-evidence-primitives--all-primitives",
  1163 |     );
  1164 |     for (const locator of [
  1165 |       story.getByTestId("authority-badge-fixture-rejection"),
  1166 |       story.getByTestId("candidate-frame"),
  1167 |       story.getByTestId("blocker-card"),
  1168 |       story.locator("#story-envelope-chip"),
  1169 |       story.locator("#story-evidence-link"),
  1170 |       story.getByTestId("provenance-popover-content"),
  1171 |       story.getByTestId("time-semantics-source-state"),
  1172 |       story.getByTestId("weakest-link-explainer"),
  1173 |     ]) {
  1174 |       await expect(locator).toBeVisible();
  1175 |     }
  1176 |     await expect(
  1177 |       story.getByTestId("authority-badge-fixture-rejection"),
  1178 |     ).toHaveAttribute("data-fixture-rejection", /fixture provenance/i);
  1179 |     await expect(story.locator("[data-authority-recognition]")).toHaveCount(0);
  1180 |     await expect(story.getByTestId("candidate-frame")).toHaveAttribute(
  1181 |       "data-authority-posture",
  1182 |       "candidate",
  1183 |     );
  1184 |     await expect(story.getByTestId("blocker-card")).toHaveAttribute(
  1185 |       "data-producer-blocker-code",
  1186 |       "fixture_missing_grounded_effect",
  1187 |     );
  1188 |     await expect(story.locator("#story-envelope-chip")).toHaveAttribute(
  1189 |       "data-fixture-authority",
  1190 |       "fixture_only",
  1191 |     );
  1192 |     await expect(story.locator("#story-evidence-link")).toHaveAttribute(
  1193 |       "data-evidence-claim",
  1194 |       "reference-only",
  1195 |     );
  1196 |     await expect(story).toHaveScreenshot("ds4-evidence-primitives.png", {
  1197 |       animations: "disabled",
  1198 |       caret: "hide",
  1199 |     });
  1200 |     await page.setViewportSize({ width: 393, height: 852 });
  1201 |     await expect(story.getByTestId("weakest-link-explainer")).toBeVisible();
  1202 |     await page.emulateMedia({
  1203 |       forcedColors: "active",
  1204 |       reducedMotion: "reduce",
  1205 |     });
  1206 |     await expect(story.locator("#story-evidence-link")).toBeVisible();
  1207 |     await page.emulateMedia({ media: "print" });
  1208 |     await expect(story.getByTestId("candidate-frame")).toBeVisible();
  1209 |   });
  1210 | 
  1211 |   test("decision packet reading view A4 print", async ({ page }) => {
  1212 |     const surface = await openPrintSurface(page, {
  1213 |       path: `/artifacts/${fixtureMetadata.decision_packet_artifact_id}?tab=content&view=reading`,
  1214 |       readyTestId: "artifact-page",
  1215 |       selector: ".monograph-layout",
  1216 |     });
  1217 |     await expect(surface).toHaveScreenshot(
  1218 |       "decision-reading-view-a4-print.png",
  1219 |       {
  1220 |         animations: "disabled",
  1221 |         caret: "hide",
  1222 |         maxDiffPixels: 100,
  1223 |       },
  1224 |     );
  1225 |   });
  1226 | 
  1227 |   test.describe("DS8 governed run paper", () => {
  1228 |     test("semantic DOM closes overview and report paper egress", async ({
  1229 |       page,
  1230 |     }) => {
  1231 |       const browserLocalSentinel = "DS8-BROWSER-LOCAL-MUST-NOT-PRINT";
  1232 |       let paperResponseCount = 0;
  1233 |       page.on("response", (response) => {
  1234 |         if (isRunPaperResponse(response.url(), fixtureMetadata.core_run_id)) {
  1235 |           paperResponseCount += 1;
  1236 |         }
  1237 |       });
  1238 | 
  1239 |       await page.goto(
  1240 |         `/runs/${fixtureMetadata.core_run_id}/overview?trust=expanded`,
  1241 |       );
  1242 |       await expect(page.getByTestId("run-detail-page")).toBeVisible();
  1243 |       const annotationPanel = page.getByTestId("annotation-surface-panel");
  1244 |       await expect(annotationPanel).toBeVisible();
  1245 |       await annotationPanel.locator("textarea").fill(browserLocalSentinel);
  1246 |       await annotationPanel.locator('form button[type="submit"]').click();
  1247 |       await expect(
  1248 |         annotationPanel.getByText(browserLocalSentinel),
> 1249 |       ).toBeVisible();
       |         ^ Error: expect(locator).toBeVisible() failed
  1250 | 
  1251 |       await page.emulateMedia({ media: "print" });
  1252 |       await expect(page.getByTestId("run-detail-page")).toBeHidden();
  1253 |       await expect(
  1254 |         page.locator('[data-paper-payload="run-paper"]'),
  1255 |       ).toHaveCount(0);
  1256 |       await expect(page.getByText(browserLocalSentinel)).toBeHidden();
  1257 |       const overviewEgress = await censusVisiblePrintEgress(page);
  1258 |       expect(overviewEgress.controls).toEqual([]);
  1259 |       expect(overviewEgress.hudAndCraft).toEqual([]);
  1260 |       expect(overviewEgress.links).toEqual([]);
  1261 |       expect(overviewEgress.text).not.toContain(browserLocalSentinel);
  1262 | 
  1263 |       const { packet, rawBytes } = await openRunPaper(
  1264 |         page,
  1265 |         fixtureMetadata.core_run_id,
  1266 |       );
  1267 |       const documentRoot = page.getByTestId("run-paper-document");
  1268 |       await expect(documentRoot).toBeVisible();
  1269 |       await expect(documentRoot.getByText(browserLocalSentinel)).toHaveCount(0);
  1270 |       await expect(
  1271 |         documentRoot.locator(
  1272 |           'button, input, select, textarea, [role="slider"], [contenteditable]:not([contenteditable="false"])',
  1273 |         ),
  1274 |       ).toHaveCount(0);
  1275 |       await expect(
  1276 |         documentRoot.getByTestId("operator-craft-panel"),
  1277 |       ).toHaveCount(0);
  1278 |       await expect(
  1279 |         documentRoot.getByTestId("ambient-telemetry-hud"),
  1280 |       ).toHaveCount(0);
  1281 |       await expect(
  1282 |         documentRoot.locator('a[href^="/public/decisions/"]'),
  1283 |       ).toHaveCount(0);
  1284 |       expect(new TextDecoder().decode(rawBytes)).not.toContain(
  1285 |         browserLocalSentinel,
  1286 |       );
  1287 | 
  1288 |       for (const [field, expectedValue] of expectedRunPaperFields(packet)) {
  1289 |         const fact = documentRoot.locator(`[data-run-paper-field="${field}"]`);
  1290 |         await expect(fact, `paper field ${field}`).toHaveCount(1);
  1291 |         await expect(fact.locator("dd"), `paper field ${field}`).toHaveText(
  1292 |           expectedValue,
  1293 |         );
  1294 |       }
  1295 |       expectAuthorityAbstainingRunPaper(packet);
  1296 |       await expect(
  1297 |         documentRoot.getByTestId("run-paper-case-authority-abstaining"),
  1298 |       ).toBeVisible();
  1299 |       await expect(
  1300 |         documentRoot.locator("[data-run-paper-authority-nonreceipt]"),
  1301 |       ).toHaveCount(3);
  1302 | 
  1303 |       const reportEgress = await censusVisiblePrintEgress(page);
  1304 |       expect(reportEgress.controls).toEqual([]);
  1305 |       expect(reportEgress.hudAndCraft).toEqual([]);
  1306 |       expect(reportEgress.text).not.toContain(browserLocalSentinel);
  1307 |       expect(
  1308 |         reportEgress.links.filter((link) =>
  1309 |           link.href?.startsWith("/public/decisions/"),
  1310 |         ),
  1311 |       ).toEqual([]);
  1312 |       expect(reportEgress.links).toEqual(
  1313 |         packet.artifact_links.map((link) => ({
  1314 |           artifactId: link.artifact_ref.artifact_id,
  1315 |           href: link.href,
  1316 |           paperEligible: "true",
  1317 |           printedTarget: expect.stringContaining(link.href),
  1318 |         })),
  1319 |       );
  1320 | 
  1321 |       await page.emulateMedia({ media: "screen" });
  1322 |       const downloadPromise = page.waitForEvent("download");
  1323 |       await page.getByRole("button", { name: "Export MACHINE packet" }).click();
  1324 |       const download = await downloadPromise;
  1325 |       const downloadPath = await download.path();
  1326 |       if (!downloadPath) {
  1327 |         throw new Error("MACHINE packet download did not produce a local file");
  1328 |       }
  1329 |       expect(await readFile(downloadPath)).toEqual(rawBytes);
  1330 |       expect(paperResponseCount).toBe(1);
  1331 |     });
  1332 | 
  1333 |     test("PDF keeps every page A4 and admitted growth adds pages", async ({
  1334 |       page,
  1335 |     }, testInfo) => {
  1336 |       await page.emulateMedia({ media: "print" });
  1337 |       const empty = await openRunPaper(
  1338 |         page,
  1339 |         fixtureMetadata.run_paper_empty_run_id,
  1340 |       );
  1341 |       await waitForRunPaperPdfReady(page);
  1342 |       expectAuthorityAbstainingRunPaper(empty.packet);
  1343 |       expect(empty.packet.artifact_links).toHaveLength(3);
  1344 |       await expect(page.locator("[data-run-paper-artifact-link]")).toHaveCount(
  1345 |         empty.packet.artifact_links.length,
  1346 |       );
  1347 |       expect((await censusVisiblePrintEgress(page)).links).toEqual(
  1348 |         empty.packet.artifact_links.map((link) => ({
  1349 |           artifactId: link.artifact_ref.artifact_id,
```