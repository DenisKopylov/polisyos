# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: runtime-dashboard.visual.spec.ts >> runtime-dashboard visual baselines >> DS8 governed run paper >> bounded identity A4 print
- Location: e2e/runtime-dashboard.visual.spec.ts:1409:5

# Error details

```
Error: expect(locator).toHaveScreenshot(expected) failed

Locator: locator('[data-testid="run-paper-identity"]')
  Expected an image 746px by 84px, received 746px by 332px. 1490 pixels (ratio 0.01 of all image pixels) are different.

  Snapshot: run-report-identity-a4-print.png

Call log:
  - Expect "toHaveScreenshot(run-report-identity-a4-print.png)" with timeout 5000ms
    - verifying given screenshot expectation
  - waiting for locator('[data-testid="run-paper-identity"]')
    - locator resolved to <header data-print-keep-together="true" data-testid="run-paper-identity" class="border-line space-y-3 border-b pb-4">…</header>
  - taking element screenshot
    - disabled all CSS animations
  - waiting for fonts to load...
  - fonts loaded
  - attempting scroll into view action
    - waiting for element to be stable
  - Expected an image 746px by 84px, received 746px by 332px. 1490 pixels (ratio 0.01 of all image pixels) are different.
  - waiting 100ms before taking screenshot
  - waiting for locator('[data-testid="run-paper-identity"]')
    - locator resolved to <header data-print-keep-together="true" data-testid="run-paper-identity" class="border-line space-y-3 border-b pb-4">…</header>
  - taking element screenshot
    - disabled all CSS animations
  - waiting for fonts to load...
  - fonts loaded
  - attempting scroll into view action
    - waiting for element to be stable
  - captured a stable screenshot
  - Expected an image 746px by 84px, received 746px by 332px. 1490 pixels (ratio 0.01 of all image pixels) are different.

```

# Page snapshot

```yaml
- generic [ref=e2]:
  - generic [ref=e3]:
    - text: (#main-content)
    - generic [ref=e5]:
      - text: (/) (/compose) (/runs) (/evidence) (/knowledge) (/platform)
      - generic [ref=e6]:
        - banner [ref=e7]:
          - generic [ref=e8]:
            - generic [ref=e9]:
              - img [ref=e10]
              - generic [ref=e15]: Atlas analyst shell
            - paragraph [ref=e16]: Run analysis
            - heading "Decision workspace turns artifacts into one operating view" [level=2] [ref=e17]
            - paragraph [ref=e18]: Inspect run lifecycle, decisions, governance, and provenance in one workspace.
          - text: (/runs) (/compose)
        - generic [ref=e19]:
          - slider "Temporal cursor" [ref=e21] [cursor=pointer]: "1788285600000"
          - generic [ref=e29]:
            - generic [ref=e32]: Observed
            - generic [ref=e35]: Simulated
          - button "Now" [ref=e36]:
            - img [ref=e37]
            - generic [ref=e40]: Now
          - generic [ref=e42]: September 1, 2026
        - main [active] [ref=e43]:
          - generic [ref=e46]:
            - generic [ref=e47]:
              - paragraph [ref=e48]: Replay-bound decision report
              - heading "Run R_run_paper_empty_001" [level=1] [ref=e49]
              - generic [ref=e50]:
                - generic [ref=e51]:
                  - term [ref=e52]: "Policy valid at:"
                  - definition [ref=e53]: unknown
                - generic [ref=e54]:
                  - term [ref=e55]: "Knowledge tx at:"
                  - definition [ref=e56]: unknown
                - generic [ref=e57]:
                  - term [ref=e58]: "Payload as of:"
                  - definition [ref=e59]: unknown
                - generic [ref=e60]:
                  - term [ref=e61]: "Source as of:"
                  - definition [ref=e62]: unknown
                - generic [ref=e63]:
                  - term [ref=e64]: "Observed at:"
                  - definition [ref=e65]: unknown
                - generic [ref=e66]:
                  - term [ref=e67]: "Source state:"
                  - definition [ref=e68]: unknown
                - generic [ref=e69]:
                  - term [ref=e70]: "Claim as of:"
                  - definition [ref=e71]: owner_time_not_established
                - generic [ref=e72]:
                  - term [ref=e73]: "Epoch:"
                  - definition [ref=e74]: Epoch not established
                - generic [ref=e75]:
                  - term [ref=e76]: "Epoch status:"
                  - definition [ref=e77]: not established
                - generic [ref=e78]:
                  - term [ref=e79]: "Validity:"
                  - definition [ref=e80]: not established
                - generic [ref=e81]:
                  - term [ref=e82]: "Revalidation:"
                  - definition [ref=e83]: not required
                - generic [ref=e84]:
                  - term [ref=e85]: "Cache age:"
                  - definition [ref=e86]: unknown (unrecognized)
            - generic [ref=e88]:
              - generic [ref=e89]:
                - term [ref=e90]: Packet schema
                - definition [ref=e91]: policyos.runtime.run_paper_packet.v1
              - generic [ref=e92]:
                - term [ref=e93]: Projection rule
                - definition [ref=e94]: policyos.runtime.run_paper.v1
              - generic [ref=e95]:
                - term [ref=e96]: Projection hash
                - definition [ref=e97]: sha256:97f5ed0b652f169ab275acbe74527e4a6b365af7cfd5d72d0b977e00c30d1e3a
              - generic [ref=e98]:
                - term [ref=e99]: Intended audiences
                - definition [ref=e100]: reviewer, expert
              - generic [ref=e101]:
                - term [ref=e102]: Manifest
                - definition [ref=e103]: sha256:f42083f9985afabcee9bb4320b727525f74ac5067162daa4b3be4109dd0bf051
              - generic [ref=e104]:
                - term [ref=e105]: Manifest schema version
                - definition [ref=e106]: 0.1.0
              - generic [ref=e107]:
                - term [ref=e108]: Replay projection rule
                - definition [ref=e109]: policyos.runtime.run_paper.v1
              - generic [ref=e110]:
                - term [ref=e111]: Replay projection hash
                - definition [ref=e112]: sha256:97f5ed0b652f169ab275acbe74527e4a6b365af7cfd5d72d0b977e00c30d1e3a
            - generic [ref=e113]:
              - heading "Run state" [level=2] [ref=e114]
              - generic [ref=e115]:
                - generic [ref=e116]:
                  - term [ref=e117]: Status
                  - definition [ref=e118]: completed
                - generic [ref=e119]:
                  - term [ref=e120]: Terminality
                  - definition [ref=e121]: terminal
                - generic [ref=e122]:
                  - term [ref=e123]: Source kind
                  - definition [ref=e124]: core_run
                - generic [ref=e125]:
                  - term [ref=e126]: Tenant
                  - definition [ref=e127]: aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa
                - generic [ref=e128]:
                  - term [ref=e129]: Cell
                  - definition [ref=e130]: cell-a
                - generic [ref=e131]:
                  - term [ref=e132]: Started at
                  - definition [ref=e133]: 2026-01-01T00:00:00Z
                - generic [ref=e134]:
                  - term [ref=e135]: Finished at
                  - definition [ref=e136]: 2026-01-01T00:05:00Z
                - generic [ref=e137]:
                  - term [ref=e138]: Duration (ms)
                  - definition [ref=e139]: "300000"
            - generic [ref=e140]:
              - heading "Case and DesignRecord" [level=2] [ref=e141]
              - generic [ref=e142]:
                - generic [ref=e143]:
                  - term [ref=e144]: Availability
                  - definition [ref=e145]: record_available_authority_abstaining
                - generic [ref=e146]:
                  - term [ref=e147]: Authority projection
                  - definition [ref=e148]: abstained
                - generic [ref=e149]:
                  - term [ref=e150]: Case
                  - definition [ref=e151]: ukrainian_msme_credit_constructs__dashboard_empty
                - generic [ref=e152]:
                  - term [ref=e153]: Run binding
                  - definition [ref=e154]: run-bound-s2-ead90488ab11802a4e22f1da
                - generic [ref=e155]:
                  - term [ref=e156]: DesignRecord
                  - definition [ref=e157]: layer2.s2.design_record.ukrainian_msme_credit_constructs__dashboard_empty
                - generic [ref=e158]:
                  - term [ref=e159]: DesignRecord artifact
                  - definition [ref=e160]: sha256:d920d8d919fdadc351245a958b03aed1fdd42ffceb29da0831b5da57b9dfdb6c
                - generic [ref=e161]:
                  - term [ref=e162]: Search ledger artifact
                  - definition [ref=e163]: sha256:3f74b198b50f02022eff3b30993b0b4149781bdee3d260d45e8aea1c2cdb7025
                - generic [ref=e164]:
                  - term [ref=e165]: Run
                  - definition [ref=e166]: R_run_paper_empty_001
                - generic [ref=e167]:
                  - term [ref=e168]: Tenant
                  - definition [ref=e169]: aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa
                - generic [ref=e170]:
                  - term [ref=e171]: Cell
                  - definition [ref=e172]: cell-a
              - generic [ref=e173]:
                - heading "grounding" [level=3] [ref=e174]
                - generic [ref=e175]:
                  - generic [ref=e176]:
                    - term [ref=e177]: Missing authority
                    - definition [ref=e178]: generation_cycle_grounding_authority
                  - generic [ref=e179]:
                    - term [ref=e180]: Status
                    - definition [ref=e181]: not_established
                  - generic [ref=e182]:
                    - term [ref=e183]: Authority state
                    - definition [ref=e184]: absent/unallocated
                  - generic [ref=e185]:
                    - term [ref=e186]: Owner route
                    - definition [ref=e187]: polisyos.runtime.quality.generation_cycle.GroundingStatus
                - list [ref=e188]:
                  - listitem [ref=e189]: grounding_state
                  - listitem [ref=e190]: grounded_case_projection
                  - listitem [ref=e191]: available_run_paper_case
              - generic [ref=e192]:
                - heading "admission" [level=3] [ref=e193]
                - generic [ref=e194]:
                  - generic [ref=e195]:
                    - term [ref=e196]: Missing authority
                    - definition [ref=e197]: hypothesis_ledger_admission_authority
                  - generic [ref=e198]:
                    - term [ref=e199]: Status
                    - definition [ref=e200]: not_established
                  - generic [ref=e201]:
                    - term [ref=e202]: Authority state
                    - definition [ref=e203]: absent/unallocated
                  - generic [ref=e204]:
                    - term [ref=e205]: Owner route
                    - definition [ref=e206]: polisyos.runtime.quality.hypothesis_ledger.HypothesisAdmissionState
                - list [ref=e207]:
                  - listitem [ref=e208]: admission_state
                  - listitem [ref=e209]: admitted_case_projection
                  - listitem [ref=e210]: available_run_paper_case
              - generic [ref=e211]:
                - heading "promotion" [level=3] [ref=e212]
                - generic [ref=e213]:
                  - generic [ref=e214]:
                    - term [ref=e215]: Missing authority
                    - definition [ref=e216]: layer3_g4_promotion_authority
                  - generic [ref=e217]:
                    - term [ref=e218]: Status
                    - definition [ref=e219]: not_established
                  - generic [ref=e220]:
                    - term [ref=e221]: Authority state
                    - definition [ref=e222]: absent/unallocated
                  - generic [ref=e223]:
                    - term [ref=e224]: Owner route
                    - definition [ref=e225]: polisyos.runtime.quality.proving_ground.governed_promotion_gate.Layer3G4PromotionRecord.promotion_state
                - list [ref=e226]:
                  - listitem [ref=e227]: promotion_state
                  - listitem [ref=e228]: governed_case_projection
                  - listitem [ref=e229]: available_run_paper_case
            - generic [ref=e230]:
              - heading "Stage trace" [level=2] [ref=e231]
              - generic [ref=e232]:
                - generic [ref=e233]:
                  - term [ref=e234]: Availability
                  - definition [ref=e235]: available
                - generic [ref=e236]:
                  - term [ref=e237]: Owner route
                  - definition [ref=e238]: core RunManifest.trace_ref
                - generic [ref=e239]:
                  - term [ref=e240]: Trace artifact
                  - definition [ref=e241]: sha256:b84dd8158412f8c2ce24e42a74c3ca6630abdb81cf2352818f7de7e50988a7e9
            - generic [ref=e242]:
              - heading "Admitted run outputs" [level=2] [ref=e243]
              - paragraph [ref=e244]: "3"
              - list [ref=e245]:
                - listitem [ref=e246]:
                  - link "policyos.layer2_s2.design_record_v0 · sha256:d920d8d919fdadc351245a958b03aed1fdd42ffceb29da0831b5da57b9dfdb6c </api/v1/artifacts/sha256:d920d8d919fdadc351245a958b03aed1fdd42ffceb29da0831b5da57b9dfdb6c>" [ref=e247] [cursor=pointer]:
                    - /url: /api/v1/artifacts/sha256:d920d8d919fdadc351245a958b03aed1fdd42ffceb29da0831b5da57b9dfdb6c
                - listitem [ref=e248]:
                  - link "policyos.layer2_s2.search_ledger · sha256:3f74b198b50f02022eff3b30993b0b4149781bdee3d260d45e8aea1c2cdb7025 </api/v1/artifacts/sha256:3f74b198b50f02022eff3b30993b0b4149781bdee3d260d45e8aea1c2cdb7025>" [ref=e249] [cursor=pointer]:
                    - /url: /api/v1/artifacts/sha256:3f74b198b50f02022eff3b30993b0b4149781bdee3d260d45e8aea1c2cdb7025
                - listitem [ref=e250]:
                  - link "policyos.pdc.run_bound_design_record_binding · sha256:8855993ab9f7e5c231f21d8fd8fa62b9b1766e8c6e286e19916c4246fcf94d65 </api/v1/artifacts/sha256:8855993ab9f7e5c231f21d8fd8fa62b9b1766e8c6e286e19916c4246fcf94d65>" [ref=e251] [cursor=pointer]:
                    - /url: /api/v1/artifacts/sha256:8855993ab9f7e5c231f21d8fd8fa62b9b1766e8c6e286e19916c4246fcf94d65
            - generic [ref=e252]:
              - heading "Complete governed packet facts" [level=2] [ref=e253]
              - generic [ref=e254]:
                - generic [ref=e255]:
                  - term [ref=e256]: /
                  - definition [ref=e257]: "[object:artifactLinks,caseRecord,intendedAudiences,packetSchemaVersion,projectionHash,projectionRuleVersion,replayAddress,replayPins,reportHref,run,source,stableAddress,stageTrace]"
                - generic [ref=e258]:
                  - term [ref=e259]: /artifactLinks
                  - definition [ref=e260]: "[array:3]"
                - generic [ref=e261]:
                  - term [ref=e262]: /artifactLinks/0
                  - definition [ref=e263]: "[object:artifact_ref,href,relation]"
                - generic [ref=e264]:
                  - term [ref=e265]: /artifactLinks/0/artifact_ref
                  - definition [ref=e266]: "[object:artifact_id,kind,media_type]"
                - generic [ref=e267]:
                  - term [ref=e268]: /artifactLinks/0/artifact_ref/artifact_id
                  - definition [ref=e269]: sha256:d920d8d919fdadc351245a958b03aed1fdd42ffceb29da0831b5da57b9dfdb6c
                - generic [ref=e270]:
                  - term [ref=e271]: /artifactLinks/0/artifact_ref/kind
                  - definition [ref=e272]: policyos.layer2_s2.design_record_v0
                - generic [ref=e273]:
                  - term [ref=e274]: /artifactLinks/0/artifact_ref/media_type
                  - definition [ref=e275]: application/json
                - generic [ref=e276]:
                  - term [ref=e277]: /artifactLinks/0/href
                  - definition [ref=e278]: /api/v1/artifacts/sha256:d920d8d919fdadc351245a958b03aed1fdd42ffceb29da0831b5da57b9dfdb6c
                - generic [ref=e279]:
                  - term [ref=e280]: /artifactLinks/0/relation
                  - definition [ref=e281]: run_output
                - generic [ref=e282]:
                  - term [ref=e283]: /artifactLinks/1
                  - definition [ref=e284]: "[object:artifact_ref,href,relation]"
                - generic [ref=e285]:
                  - term [ref=e286]: /artifactLinks/1/artifact_ref
                  - definition [ref=e287]: "[object:artifact_id,kind,media_type]"
                - generic [ref=e288]:
                  - term [ref=e289]: /artifactLinks/1/artifact_ref/artifact_id
                  - definition [ref=e290]: sha256:3f74b198b50f02022eff3b30993b0b4149781bdee3d260d45e8aea1c2cdb7025
                - generic [ref=e291]:
                  - term [ref=e292]: /artifactLinks/1/artifact_ref/kind
                  - definition [ref=e293]: policyos.layer2_s2.search_ledger
                - generic [ref=e294]:
                  - term [ref=e295]: /artifactLinks/1/artifact_ref/media_type
                  - definition [ref=e296]: application/json
                - generic [ref=e297]:
                  - term [ref=e298]: /artifactLinks/1/href
                  - definition [ref=e299]: /api/v1/artifacts/sha256:3f74b198b50f02022eff3b30993b0b4149781bdee3d260d45e8aea1c2cdb7025
                - generic [ref=e300]:
                  - term [ref=e301]: /artifactLinks/1/relation
                  - definition [ref=e302]: run_output
                - generic [ref=e303]:
                  - term [ref=e304]: /artifactLinks/2
                  - definition [ref=e305]: "[object:artifact_ref,href,relation]"
                - generic [ref=e306]:
                  - term [ref=e307]: /artifactLinks/2/artifact_ref
                  - definition [ref=e308]: "[object:artifact_id,kind,media_type]"
                - generic [ref=e309]:
                  - term [ref=e310]: /artifactLinks/2/artifact_ref/artifact_id
                  - definition [ref=e311]: sha256:8855993ab9f7e5c231f21d8fd8fa62b9b1766e8c6e286e19916c4246fcf94d65
                - generic [ref=e312]:
                  - term [ref=e313]: /artifactLinks/2/artifact_ref/kind
                  - definition [ref=e314]: policyos.pdc.run_bound_design_record_binding
                - generic [ref=e315]:
                  - term [ref=e316]: /artifactLinks/2/artifact_ref/media_type
                  - definition [ref=e317]: application/json
                - generic [ref=e318]:
                  - term [ref=e319]: /artifactLinks/2/href
                  - definition [ref=e320]: /api/v1/artifacts/sha256:8855993ab9f7e5c231f21d8fd8fa62b9b1766e8c6e286e19916c4246fcf94d65
                - generic [ref=e321]:
                  - term [ref=e322]: /artifactLinks/2/relation
                  - definition [ref=e323]: run_output
                - generic [ref=e324]:
                  - term [ref=e325]: /caseRecord
                  - definition [ref=e326]: "[object:admission_nonreceipt,authority_projection,availability,case_id,design_record,design_record_binding,grounding_nonreceipt,promotion_nonreceipt]"
                - generic [ref=e327]:
                  - term [ref=e328]: /caseRecord/admission_nonreceipt
                  - definition [ref=e329]: "[object:authority_state,denied_uses,kind,missing_authority,owner_route,status]"
                - generic [ref=e330]:
                  - term [ref=e331]: /caseRecord/admission_nonreceipt/authority_state
                  - definition [ref=e332]: absent/unallocated
                - generic [ref=e333]:
                  - term [ref=e334]: /caseRecord/admission_nonreceipt/denied_uses
                  - definition [ref=e335]: "[array:3]"
                - generic [ref=e336]:
                  - term [ref=e337]: /caseRecord/admission_nonreceipt/denied_uses/0
                  - definition [ref=e338]: admission_state
                - generic [ref=e339]:
                  - term [ref=e340]: /caseRecord/admission_nonreceipt/denied_uses/1
                  - definition [ref=e341]: admitted_case_projection
                - generic [ref=e342]:
                  - term [ref=e343]: /caseRecord/admission_nonreceipt/denied_uses/2
                  - definition [ref=e344]: available_run_paper_case
                - generic [ref=e345]:
                  - term [ref=e346]: /caseRecord/admission_nonreceipt/kind
                  - definition [ref=e347]: run_paper_authority_nonreceipt
                - generic [ref=e348]:
                  - term [ref=e349]: /caseRecord/admission_nonreceipt/missing_authority
                  - definition [ref=e350]: hypothesis_ledger_admission_authority
                - generic [ref=e351]:
                  - term [ref=e352]: /caseRecord/admission_nonreceipt/owner_route
                  - definition [ref=e353]: polisyos.runtime.quality.hypothesis_ledger.HypothesisAdmissionState
                - generic [ref=e354]:
                  - term [ref=e355]: /caseRecord/admission_nonreceipt/status
                  - definition [ref=e356]: not_established
                - generic [ref=e357]:
                  - term [ref=e358]: /caseRecord/authority_projection
                  - definition [ref=e359]: abstained
                - generic [ref=e360]:
                  - term [ref=e361]: /caseRecord/availability
                  - definition [ref=e362]: record_available_authority_abstaining
                - generic [ref=e363]:
                  - term [ref=e364]: /caseRecord/case_id
                  - definition [ref=e365]: ukrainian_msme_credit_constructs__dashboard_empty
                - generic [ref=e366]:
                  - term [ref=e367]: /caseRecord/design_record
                  - definition [ref=e368]: "[object:authority_boundary,axis_positions,candidate_ref,candidate_source,envelope,firewall_status,ledger_refs,projection_audiences,projection_status,record_id,schema_version]"
                - generic [ref=e369]:
                  - term [ref=e370]: /caseRecord/design_record/authority_boundary
                  - definition [ref=e371]: "[object:authoritative_for,boundary_id,decision_grade,evidence_basis,evidence_kind,known_limits,may_not_use_for,posture,rule_version_refs,source_authority]"
                - generic [ref=e372]:
                  - term [ref=e373]: /caseRecord/design_record/authority_boundary/authoritative_for
                  - definition [ref=e374]: "[array:3]"
                - generic [ref=e375]:
                  - term [ref=e376]: /caseRecord/design_record/authority_boundary/authoritative_for/0
                  - definition [ref=e377]: shadow_design_search_replay
                - generic [ref=e378]:
                  - term [ref=e379]: /caseRecord/design_record/authority_boundary/authoritative_for/1
                  - definition [ref=e380]: machine_replay_trace
                - generic [ref=e381]:
                  - term [ref=e382]: /caseRecord/design_record/authority_boundary/authoritative_for/2
                  - definition [ref=e383]: reviewer_search_trace
                - generic [ref=e384]:
                  - term [ref=e385]: /caseRecord/design_record/authority_boundary/boundary_id
                  - definition [ref=e386]: "null"
                - generic [ref=e387]:
                  - term [ref=e388]: /caseRecord/design_record/authority_boundary/decision_grade
                  - definition [ref=e389]: "null"
                - generic [ref=e390]:
                  - term [ref=e391]: /caseRecord/design_record/authority_boundary/evidence_basis
                  - definition [ref=e392]: "null"
                - generic [ref=e393]:
                  - term [ref=e394]: /caseRecord/design_record/authority_boundary/evidence_kind
                  - definition [ref=e395]: "null"
                - generic [ref=e396]:
                  - term [ref=e397]: /caseRecord/design_record/authority_boundary/known_limits
                  - definition [ref=e398]: "[array:0]"
                - generic [ref=e399]:
                  - term [ref=e400]: /caseRecord/design_record/authority_boundary/may_not_use_for
                  - definition [ref=e401]: "[array:8]"
                - generic [ref=e402]:
                  - term [ref=e403]: /caseRecord/design_record/authority_boundary/may_not_use_for/0
                  - definition [ref=e404]: production_recommendation
                - generic [ref=e405]:
                  - term [ref=e406]: /caseRecord/design_record/authority_boundary/may_not_use_for/1
                  - definition [ref=e407]: publication_authority
                - generic [ref=e408]:
                  - term [ref=e409]: /caseRecord/design_record/authority_boundary/may_not_use_for/2
                  - definition [ref=e410]: rollout_authority
                - generic [ref=e411]:
                  - term [ref=e412]: /caseRecord/design_record/authority_boundary/may_not_use_for/3
                  - definition [ref=e413]: claim_authority
                - generic [ref=e414]:
                  - term [ref=e415]: /caseRecord/design_record/authority_boundary/may_not_use_for/4
                  - definition [ref=e416]: production_claim_authority
                - generic [ref=e417]:
                  - term [ref=e418]: /caseRecord/design_record/authority_boundary/may_not_use_for/5
                  - definition [ref=e419]: production_closeout_authority
                - generic [ref=e420]:
                  - term [ref=e421]: /caseRecord/design_record/authority_boundary/may_not_use_for/6
                  - definition [ref=e422]: acquisition_authority
                - generic [ref=e423]:
                  - term [ref=e424]: /caseRecord/design_record/authority_boundary/may_not_use_for/7
                  - definition [ref=e425]: source_contract_authority
                - generic [ref=e426]:
                  - term [ref=e427]: /caseRecord/design_record/authority_boundary/posture
                  - definition [ref=e428]: shadow
                - generic [ref=e429]:
                  - term [ref=e430]: /caseRecord/design_record/authority_boundary/rule_version_refs
                  - definition [ref=e431]: "[array:1]"
                - generic [ref=e432]:
                  - term [ref=e433]: /caseRecord/design_record/authority_boundary/rule_version_refs/0
                  - definition [ref=e434]: policyos.layer2.s2.design_search.v1
                - generic [ref=e435]:
                  - term [ref=e436]: /caseRecord/design_record/authority_boundary/source_authority
                  - definition [ref=e437]: deterministic_producer
                - generic [ref=e438]:
                  - term [ref=e439]: /caseRecord/design_record/axis_positions
                  - definition [ref=e440]: "[array:2]"
                - generic [ref=e441]:
                  - term [ref=e442]: /caseRecord/design_record/axis_positions/0
                  - definition [ref=e443]: "[object:authority_purpose,axis,cluster,evidence_refs,position,rule_version_ref]"
                - generic [ref=e444]:
                  - term [ref=e445]: /caseRecord/design_record/axis_positions/0/authority_purpose
                  - definition [ref=e446]: shadow_design_search_replay
                - generic [ref=e447]:
                  - term [ref=e448]: /caseRecord/design_record/axis_positions/0/axis
                  - definition [ref=e449]: design_grammar
                - generic [ref=e450]:
                  - term [ref=e451]: /caseRecord/design_record/axis_positions/0/cluster
                  - definition [ref=e452]: INTERVENTION
                - generic [ref=e453]:
                  - term [ref=e454]: /caseRecord/design_record/axis_positions/0/evidence_refs
                  - definition [ref=e455]: "[array:1]"
                - generic [ref=e456]:
                  - term [ref=e457]: /caseRecord/design_record/axis_positions/0/evidence_refs/0
                  - definition [ref=e458]: pdc://layer2/s2/ukrainian_msme_credit_constructs__dashboard_empty/grammar-expansion
                - generic [ref=e459]:
                  - term [ref=e460]: /caseRecord/design_record/axis_positions/0/position
                  - definition [ref=e461]: grammar_expanded_shadow_only
                - generic [ref=e462]:
                  - term [ref=e463]: /caseRecord/design_record/axis_positions/0/rule_version_ref
                  - definition [ref=e464]: policyos.layer2.s2.design_search.v1
                - generic [ref=e465]:
                  - term [ref=e466]: /caseRecord/design_record/axis_positions/1
                  - definition [ref=e467]: "[object:authority_purpose,axis,cluster,evidence_refs,position,rule_version_ref]"
                - generic [ref=e468]:
                  - term [ref=e469]: /caseRecord/design_record/axis_positions/1/authority_purpose
                  - definition [ref=e470]: shadow_design_search_replay
                - generic [ref=e471]:
                  - term [ref=e472]: /caseRecord/design_record/axis_positions/1/axis
                  - definition [ref=e473]: design_candidate
                - generic [ref=e474]:
                  - term [ref=e475]: /caseRecord/design_record/axis_positions/1/cluster
                  - definition [ref=e476]: INTERVENTION
                - generic [ref=e477]:
                  - term [ref=e478]: /caseRecord/design_record/axis_positions/1/evidence_refs
                  - definition [ref=e479]: "[array:1]"
                - generic [ref=e480]:
                  - term [ref=e481]: /caseRecord/design_record/axis_positions/1/evidence_refs/0
                  - definition [ref=e482]: pdc://layer2/s2/ukrainian_msme_credit_constructs__dashboard_empty/candidate/credit_guarantee
                - generic [ref=e483]:
                  - term [ref=e484]: /caseRecord/design_record/axis_positions/1/position
                  - definition [ref=e485]: candidate_emitted_from_grammar_shadow_only
                - generic [ref=e486]:
                  - term [ref=e487]: /caseRecord/design_record/axis_positions/1/rule_version_ref
                  - definition [ref=e488]: policyos.layer2.s2.design_search.v1
                - generic [ref=e489]:
                  - term [ref=e490]: /caseRecord/design_record/candidate_ref
                  - definition [ref=e491]: pdc://layer2/s2/ukrainian_msme_credit_constructs__dashboard_empty/candidate/credit_guarantee
                - generic [ref=e492]:
                  - term [ref=e493]: /caseRecord/design_record/candidate_source
                  - definition [ref=e494]: deterministic_producer
                - generic [ref=e495]:
                  - term [ref=e496]: /caseRecord/design_record/envelope
                  - definition [ref=e497]: "[object:actor_scopes,certified_for,cluster_authority_dimension_refs,domains,envelope_id,epistemic_regime_scopes,method_scopes,not_certified_for,posture_scopes,rule_version_ref]"
                - generic [ref=e498]:
                  - term [ref=e499]: /caseRecord/design_record/envelope/actor_scopes
                  - definition [ref=e500]: "[array:1]"
                - generic [ref=e501]:
                  - term [ref=e502]: /caseRecord/design_record/envelope/actor_scopes/0
                  - definition [ref=e503]: actor://ua/ministry-of-economy
                - generic [ref=e504]:
                  - term [ref=e505]: /caseRecord/design_record/envelope/certified_for
                  - definition [ref=e506]: "[array:3]"
                - generic [ref=e507]:
                  - term [ref=e508]: /caseRecord/design_record/envelope/certified_for/0
                  - definition [ref=e509]: shadow_design_search_replay
                - generic [ref=e510]:
                  - term [ref=e511]: /caseRecord/design_record/envelope/certified_for/1
                  - definition [ref=e512]: machine_replay_trace
                - generic [ref=e513]:
                  - term [ref=e514]: /caseRecord/design_record/envelope/certified_for/2
                  - definition [ref=e515]: reviewer_search_trace
                - generic [ref=e516]:
                  - term [ref=e517]: /caseRecord/design_record/envelope/cluster_authority_dimension_refs
                  - definition [ref=e518]: "[array:0]"
                - generic [ref=e519]:
                  - term [ref=e520]: /caseRecord/design_record/envelope/domains
                  - definition [ref=e521]: "[array:1]"
                - generic [ref=e522]:
                  - term [ref=e523]: /caseRecord/design_record/envelope/domains/0
                  - definition [ref=e524]: ukrainian_msme_credit
                - generic [ref=e525]:
                  - term [ref=e526]: /caseRecord/design_record/envelope/envelope_id
                  - definition [ref=e527]: layer2.s2.envelope.ukrainian_msme_credit_constructs__dashboard_empty
                - generic [ref=e528]:
                  - term [ref=e529]: /caseRecord/design_record/envelope/epistemic_regime_scopes
                  - definition [ref=e530]: "[array:1]"
                - generic [ref=e531]:
                  - term [ref=e532]: /caseRecord/design_record/envelope/epistemic_regime_scopes/0
                  - definition [ref=e533]: ignorance
                - generic [ref=e534]:
                  - term [ref=e535]: /caseRecord/design_record/envelope/method_scopes
                  - definition [ref=e536]: "[array:1]"
                - generic [ref=e537]:
                  - term [ref=e538]: /caseRecord/design_record/envelope/method_scopes/0
                  - definition [ref=e539]: deterministic_shadow_design_search
                - generic [ref=e540]:
                  - term [ref=e541]: /caseRecord/design_record/envelope/not_certified_for
                  - definition [ref=e542]: "[array:8]"
                - generic [ref=e543]:
                  - term [ref=e544]: /caseRecord/design_record/envelope/not_certified_for/0
                  - definition [ref=e545]: production_recommendation
                - generic [ref=e546]:
                  - term [ref=e547]: /caseRecord/design_record/envelope/not_certified_for/1
                  - definition [ref=e548]: publication_authority
                - generic [ref=e549]:
                  - term [ref=e550]: /caseRecord/design_record/envelope/not_certified_for/2
                  - definition [ref=e551]: rollout_authority
                - generic [ref=e552]:
                  - term [ref=e553]: /caseRecord/design_record/envelope/not_certified_for/3
                  - definition [ref=e554]: claim_authority
                - generic [ref=e555]:
                  - term [ref=e556]: /caseRecord/design_record/envelope/not_certified_for/4
                  - definition [ref=e557]: production_claim_authority
                - generic [ref=e558]:
                  - term [ref=e559]: /caseRecord/design_record/envelope/not_certified_for/5
                  - definition [ref=e560]: production_closeout_authority
                - generic [ref=e561]:
                  - term [ref=e562]: /caseRecord/design_record/envelope/not_certified_for/6
                  - definition [ref=e563]: acquisition_authority
                - generic [ref=e564]:
                  - term [ref=e565]: /caseRecord/design_record/envelope/not_certified_for/7
                  - definition [ref=e566]: source_contract_authority
                - generic [ref=e567]:
                  - term [ref=e568]: /caseRecord/design_record/envelope/posture_scopes
                  - definition [ref=e569]: "[array:1]"
                - generic [ref=e570]:
                  - term [ref=e571]: /caseRecord/design_record/envelope/posture_scopes/0
                  - definition [ref=e572]: shadow
                - generic [ref=e573]:
                  - term [ref=e574]: /caseRecord/design_record/envelope/rule_version_ref
                  - definition [ref=e575]: policyos.layer2.s2.design_search.v1
                - generic [ref=e576]:
                  - term [ref=e577]: /caseRecord/design_record/firewall_status
                  - definition [ref=e578]: "[array:2]"
                - generic [ref=e579]:
                  - term [ref=e580]: /caseRecord/design_record/firewall_status/0
                  - definition [ref=e581]: "[object:cell_ref,maturity,pattern_ids,reason,rule_version_ref,status]"
                - generic [ref=e582]:
                  - term [ref=e583]: /caseRecord/design_record/firewall_status/0/cell_ref
                  - definition [ref=e584]: INTERVENTION.design_grammar
                - generic [ref=e585]:
                  - term [ref=e586]: /caseRecord/design_record/firewall_status/0/maturity
                  - definition [ref=e587]: predictive
                - generic [ref=e588]:
                  - term [ref=e589]: /caseRecord/design_record/firewall_status/0/pattern_ids
                  - definition [ref=e590]: "[array:2]"
                - generic [ref=e591]:
                  - term [ref=e592]: /caseRecord/design_record/firewall_status/0/pattern_ids/0
                  - definition [ref=e593]: P10
                - generic [ref=e594]:
                  - term [ref=e595]: /caseRecord/design_record/firewall_status/0/pattern_ids/1
                  - definition [ref=e596]: P15
                - generic [ref=e597]:
                  - term [ref=e598]: /caseRecord/design_record/firewall_status/0/reason
                  - definition [ref=e599]: Grammar expansion precedes candidate emission in the S2 shadow loop.
                - generic [ref=e600]:
                  - term [ref=e601]: /caseRecord/design_record/firewall_status/0/rule_version_ref
                  - definition [ref=e602]: policyos.layer2.s2.design_search.v1
                - generic [ref=e603]:
                  - term [ref=e604]: /caseRecord/design_record/firewall_status/0/status
                  - definition [ref=e605]: pass
                - generic [ref=e606]:
                  - term [ref=e607]: /caseRecord/design_record/firewall_status/1
                  - definition [ref=e608]: "[object:cell_ref,maturity,pattern_ids,reason,rule_version_ref,status]"
                - generic [ref=e609]:
                  - term [ref=e610]: /caseRecord/design_record/firewall_status/1/cell_ref
                  - definition [ref=e611]: INTERVENTION.design_candidate
                - generic [ref=e612]:
                  - term [ref=e613]: /caseRecord/design_record/firewall_status/1/maturity
                  - definition [ref=e614]: fail_closed
                - generic [ref=e615]:
                  - term [ref=e616]: /caseRecord/design_record/firewall_status/1/pattern_ids
                  - definition [ref=e617]: "[array:2]"
                - generic [ref=e618]:
                  - term [ref=e619]: /caseRecord/design_record/firewall_status/1/pattern_ids/0
                  - definition [ref=e620]: P05
                - generic [ref=e621]:
                  - term [ref=e622]: /caseRecord/design_record/firewall_status/1/pattern_ids/1
                  - definition [ref=e623]: P25
                - generic [ref=e624]:
                  - term [ref=e625]: /caseRecord/design_record/firewall_status/1/reason
                  - definition [ref=e626]: Candidate is replay-visible but remains shadow-only and non-exhaustive.
                - generic [ref=e627]:
                  - term [ref=e628]: /caseRecord/design_record/firewall_status/1/rule_version_ref
                  - definition [ref=e629]: policyos.layer2.s2.design_search.v1
                - generic [ref=e630]:
                  - term [ref=e631]: /caseRecord/design_record/firewall_status/1/status
                  - definition [ref=e632]: warn
                - generic [ref=e633]:
                  - term [ref=e634]: /caseRecord/design_record/ledger_refs
                  - definition [ref=e635]: "[array:1]"
                - generic [ref=e636]:
                  - term [ref=e637]: /caseRecord/design_record/ledger_refs/0
                  - definition [ref=e638]: pdc://layer2/s2/ukrainian_msme_credit_constructs__dashboard_empty/search-ledger
                - generic [ref=e639]:
                  - term [ref=e640]: /caseRecord/design_record/projection_audiences
                  - definition [ref=e641]: "[array:2]"
                - generic [ref=e642]:
                  - term [ref=e643]: /caseRecord/design_record/projection_audiences/0
                  - definition [ref=e644]: MACHINE
                - generic [ref=e645]:
                  - term [ref=e646]: /caseRecord/design_record/projection_audiences/1
                  - definition [ref=e647]: REVIEWER
                - generic [ref=e648]:
                  - term [ref=e649]: /caseRecord/design_record/projection_status
                  - definition [ref=e650]: shadow
                - generic [ref=e651]:
                  - term [ref=e652]: /caseRecord/design_record/record_id
                  - definition [ref=e653]: layer2.s2.design_record.ukrainian_msme_credit_constructs__dashboard_empty
                - generic [ref=e654]:
                  - term [ref=e655]: /caseRecord/design_record/schema_version
                  - definition [ref=e656]: policyos.policy_design_case.layer2_readiness.v1
                - generic [ref=e657]:
                  - term [ref=e658]: /caseRecord/design_record_binding
                  - definition [ref=e659]: "[object:binding_id,case_id,cell_id,design_record_content_digest,design_record_record_id,design_record_ref,design_record_schema_name,design_record_schema_version,producer,run_id,schema_version,search_ledger_content_digest,search_ledger_id,search_ledger_ref,tenant_id]"
                - generic [ref=e660]:
                  - term [ref=e661]: /caseRecord/design_record_binding/binding_id
                  - definition [ref=e662]: run-bound-s2-ead90488ab11802a4e22f1da
                - generic [ref=e663]:
                  - term [ref=e664]: /caseRecord/design_record_binding/case_id
                  - definition [ref=e665]: ukrainian_msme_credit_constructs__dashboard_empty
                - generic [ref=e666]:
                  - term [ref=e667]: /caseRecord/design_record_binding/cell_id
                  - definition [ref=e668]: cell-a
                - generic [ref=e669]:
                  - term [ref=e670]: /caseRecord/design_record_binding/design_record_content_digest
                  - definition [ref=e671]: sha256:d920d8d919fdadc351245a958b03aed1fdd42ffceb29da0831b5da57b9dfdb6c
                - generic [ref=e672]:
                  - term [ref=e673]: /caseRecord/design_record_binding/design_record_record_id
                  - definition [ref=e674]: layer2.s2.design_record.ukrainian_msme_credit_constructs__dashboard_empty
                - generic [ref=e675]:
                  - term [ref=e676]: /caseRecord/design_record_binding/design_record_ref
                  - definition [ref=e677]: "[object:artifact_id,kind,media_type]"
                - generic [ref=e678]:
                  - term [ref=e679]: /caseRecord/design_record_binding/design_record_ref/artifact_id
                  - definition [ref=e680]: sha256:d920d8d919fdadc351245a958b03aed1fdd42ffceb29da0831b5da57b9dfdb6c
                - generic [ref=e681]:
                  - term [ref=e682]: /caseRecord/design_record_binding/design_record_ref/kind
                  - definition [ref=e683]: policyos.layer2_s2.design_record_v0
                - generic [ref=e684]:
                  - term [ref=e685]: /caseRecord/design_record_binding/design_record_ref/media_type
                  - definition [ref=e686]: application/json
                - generic [ref=e687]:
                  - term [ref=e688]: /caseRecord/design_record_binding/design_record_schema_name
                  - definition [ref=e689]: policyos.layer2_s2.design_record_v0
                - generic [ref=e690]:
                  - term [ref=e691]: /caseRecord/design_record_binding/design_record_schema_version
                  - definition [ref=e692]: policyos.policy_design_case.layer2_readiness.v1
                - generic [ref=e693]:
                  - term [ref=e694]: /caseRecord/design_record_binding/producer
                  - definition [ref=e695]: "[object:component,git,version]"
                - generic [ref=e696]:
                  - term [ref=e697]: /caseRecord/design_record_binding/producer/component
                  - definition [ref=e698]: polisyos.pdc.layer2_design_search
                - generic [ref=e699]:
                  - term [ref=e700]: /caseRecord/design_record_binding/producer/git
                  - definition [ref=e701]: "null"
                - generic [ref=e702]:
                  - term [ref=e703]: /caseRecord/design_record_binding/producer/version
                  - definition [ref=e704]: policyos.layer2.s2.design_search.v1
                - generic [ref=e705]:
                  - term [ref=e706]: /caseRecord/design_record_binding/run_id
                  - definition [ref=e707]: R_run_paper_empty_001
                - generic [ref=e708]:
                  - term [ref=e709]: /caseRecord/design_record_binding/schema_version
                  - definition [ref=e710]: policyos.pdc.run_bound_design_record_binding.v1
                - generic [ref=e711]:
                  - term [ref=e712]: /caseRecord/design_record_binding/search_ledger_content_digest
                  - definition [ref=e713]: sha256:3f74b198b50f02022eff3b30993b0b4149781bdee3d260d45e8aea1c2cdb7025
                - generic [ref=e714]:
                  - term [ref=e715]: /caseRecord/design_record_binding/search_ledger_id
                  - definition [ref=e716]: layer2.s2.ledger.ukrainian_msme_credit_constructs__dashboard_empty
                - generic [ref=e717]:
                  - term [ref=e718]: /caseRecord/design_record_binding/search_ledger_ref
                  - definition [ref=e719]: "[object:artifact_id,kind,media_type]"
                - generic [ref=e720]:
                  - term [ref=e721]: /caseRecord/design_record_binding/search_ledger_ref/artifact_id
                  - definition [ref=e722]: sha256:3f74b198b50f02022eff3b30993b0b4149781bdee3d260d45e8aea1c2cdb7025
                - generic [ref=e723]:
                  - term [ref=e724]: /caseRecord/design_record_binding/search_ledger_ref/kind
                  - definition [ref=e725]: policyos.layer2_s2.search_ledger
                - generic [ref=e726]:
                  - term [ref=e727]: /caseRecord/design_record_binding/search_ledger_ref/media_type
                  - definition [ref=e728]: application/json
                - generic [ref=e729]:
                  - term [ref=e730]: /caseRecord/design_record_binding/tenant_id
                  - definition [ref=e731]: aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa
                - generic [ref=e732]:
                  - term [ref=e733]: /caseRecord/grounding_nonreceipt
                  - definition [ref=e734]: "[object:authority_state,denied_uses,kind,missing_authority,owner_route,status]"
                - generic [ref=e735]:
                  - term [ref=e736]: /caseRecord/grounding_nonreceipt/authority_state
                  - definition [ref=e737]: absent/unallocated
                - generic [ref=e738]:
                  - term [ref=e739]: /caseRecord/grounding_nonreceipt/denied_uses
                  - definition [ref=e740]: "[array:3]"
                - generic [ref=e741]:
                  - term [ref=e742]: /caseRecord/grounding_nonreceipt/denied_uses/0
                  - definition [ref=e743]: grounding_state
                - generic [ref=e744]:
                  - term [ref=e745]: /caseRecord/grounding_nonreceipt/denied_uses/1
                  - definition [ref=e746]: grounded_case_projection
                - generic [ref=e747]:
                  - term [ref=e748]: /caseRecord/grounding_nonreceipt/denied_uses/2
                  - definition [ref=e749]: available_run_paper_case
                - generic [ref=e750]:
                  - term [ref=e751]: /caseRecord/grounding_nonreceipt/kind
                  - definition [ref=e752]: run_paper_authority_nonreceipt
                - generic [ref=e753]:
                  - term [ref=e754]: /caseRecord/grounding_nonreceipt/missing_authority
                  - definition [ref=e755]: generation_cycle_grounding_authority
                - generic [ref=e756]:
                  - term [ref=e757]: /caseRecord/grounding_nonreceipt/owner_route
                  - definition [ref=e758]: polisyos.runtime.quality.generation_cycle.GroundingStatus
                - generic [ref=e759]:
                  - term [ref=e760]: /caseRecord/grounding_nonreceipt/status
                  - definition [ref=e761]: not_established
                - generic [ref=e762]:
                  - term [ref=e763]: /caseRecord/promotion_nonreceipt
                  - definition [ref=e764]: "[object:authority_state,denied_uses,kind,missing_authority,owner_route,status]"
                - generic [ref=e765]:
                  - term [ref=e766]: /caseRecord/promotion_nonreceipt/authority_state
                  - definition [ref=e767]: absent/unallocated
                - generic [ref=e768]:
                  - term [ref=e769]: /caseRecord/promotion_nonreceipt/denied_uses
                  - definition [ref=e770]: "[array:3]"
                - generic [ref=e771]:
                  - term [ref=e772]: /caseRecord/promotion_nonreceipt/denied_uses/0
                  - definition [ref=e773]: promotion_state
                - generic [ref=e774]:
                  - term [ref=e775]: /caseRecord/promotion_nonreceipt/denied_uses/1
                  - definition [ref=e776]: governed_case_projection
                - generic [ref=e777]:
                  - term [ref=e778]: /caseRecord/promotion_nonreceipt/denied_uses/2
                  - definition [ref=e779]: available_run_paper_case
                - generic [ref=e780]:
                  - term [ref=e781]: /caseRecord/promotion_nonreceipt/kind
                  - definition [ref=e782]: run_paper_authority_nonreceipt
                - generic [ref=e783]:
                  - term [ref=e784]: /caseRecord/promotion_nonreceipt/missing_authority
                  - definition [ref=e785]: layer3_g4_promotion_authority
                - generic [ref=e786]:
                  - term [ref=e787]: /caseRecord/promotion_nonreceipt/owner_route
                  - definition [ref=e788]: polisyos.runtime.quality.proving_ground.governed_promotion_gate.Layer3G4PromotionRecord.promotion_state
                - generic [ref=e789]:
                  - term [ref=e790]: /caseRecord/promotion_nonreceipt/status
                  - definition [ref=e791]: not_established
                - generic [ref=e792]:
                  - term [ref=e793]: /intendedAudiences
                  - definition [ref=e794]: "[array:2]"
                - generic [ref=e795]:
                  - term [ref=e796]: /intendedAudiences/0
                  - definition [ref=e797]: reviewer
                - generic [ref=e798]:
                  - term [ref=e799]: /intendedAudiences/1
                  - definition [ref=e800]: expert
                - generic [ref=e801]:
                  - term [ref=e802]: /packetSchemaVersion
                  - definition [ref=e803]: policyos.runtime.run_paper_packet.v1
                - generic [ref=e804]:
                  - term [ref=e805]: /projectionHash
                  - definition [ref=e806]: sha256:97f5ed0b652f169ab275acbe74527e4a6b365af7cfd5d72d0b977e00c30d1e3a
                - generic [ref=e807]:
                  - term [ref=e808]: /projectionRuleVersion
                  - definition [ref=e809]: policyos.runtime.run_paper.v1
                - generic [ref=e810]:
                  - term [ref=e811]: /replayAddress
                  - definition [ref=e812]: /api/v1/runs/R_run_paper_empty_001/paper?manifest_artifact_id=sha256%3Af42083f9985afabcee9bb4320b727525f74ac5067162daa4b3be4109dd0bf051&manifest_schema_version=0.1.0&paper_projection_hash=sha256%3A97f5ed0b652f169ab275acbe74527e4a6b365af7cfd5d72d0b977e00c30d1e3a&paper_projection_rule_version=policyos.runtime.run_paper.v1
                - generic [ref=e813]:
                  - term [ref=e814]: /replayPins
                  - definition [ref=e815]: "[object:manifest_artifact_id,manifest_schema_version,paper_projection_hash,paper_projection_rule_version]"
                - generic [ref=e816]:
                  - term [ref=e817]: /replayPins/manifest_artifact_id
                  - definition [ref=e818]: sha256:f42083f9985afabcee9bb4320b727525f74ac5067162daa4b3be4109dd0bf051
                - generic [ref=e819]:
                  - term [ref=e820]: /replayPins/manifest_schema_version
                  - definition [ref=e821]: 0.1.0
                - generic [ref=e822]:
                  - term [ref=e823]: /replayPins/paper_projection_hash
                  - definition [ref=e824]: sha256:97f5ed0b652f169ab275acbe74527e4a6b365af7cfd5d72d0b977e00c30d1e3a
                - generic [ref=e825]:
                  - term [ref=e826]: /replayPins/paper_projection_rule_version
                  - definition [ref=e827]: policyos.runtime.run_paper.v1
                - generic [ref=e828]:
                  - term [ref=e829]: /reportHref
                  - definition [ref=e830]: /runs/R_run_paper_empty_001/report?manifest_artifact_id=sha256%3Af42083f9985afabcee9bb4320b727525f74ac5067162daa4b3be4109dd0bf051&manifest_schema_version=0.1.0&paper_projection_hash=sha256%3A97f5ed0b652f169ab275acbe74527e4a6b365af7cfd5d72d0b977e00c30d1e3a&paper_projection_rule_version=policyos.runtime.run_paper.v1#stage-trace
                - generic [ref=e831]:
                  - term [ref=e832]: /run
                  - definition [ref=e833]: "[object:cell_id,duration_ms,finished_at,run_id,run_terminality,source_kind,started_at,status,tenant_id]"
                - generic [ref=e834]:
                  - term [ref=e835]: /run/cell_id
                  - definition [ref=e836]: cell-a
                - generic [ref=e837]:
                  - term [ref=e838]: /run/duration_ms
                  - definition [ref=e839]: "300000"
                - generic [ref=e840]:
                  - term [ref=e841]: /run/finished_at
                  - definition [ref=e842]: 2026-01-01T00:05:00Z
                - generic [ref=e843]:
                  - term [ref=e844]: /run/run_id
                  - definition [ref=e845]: R_run_paper_empty_001
                - generic [ref=e846]:
                  - term [ref=e847]: /run/run_terminality
                  - definition [ref=e848]: terminal
                - generic [ref=e849]:
                  - term [ref=e850]: /run/source_kind
                  - definition [ref=e851]: core_run
                - generic [ref=e852]:
                  - term [ref=e853]: /run/started_at
                  - definition [ref=e854]: 2026-01-01T00:00:00Z
                - generic [ref=e855]:
                  - term [ref=e856]: /run/status
                  - definition [ref=e857]: completed
                - generic [ref=e858]:
                  - term [ref=e859]: /run/tenant_id
                  - definition [ref=e860]: aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa
                - generic [ref=e861]:
                  - term [ref=e862]: /source
                  - definition [ref=e863]: "[object:environment,manifest_ref,manifest_schema_name,manifest_schema_version,producer,registry_bundle]"
                - generic [ref=e864]:
                  - term [ref=e865]: /source/environment
                  - definition [ref=e866]: "null"
                - generic [ref=e867]:
                  - term [ref=e868]: /source/manifest_ref
                  - definition [ref=e869]: "[object:artifact_id,kind,media_type]"
                - generic [ref=e870]:
                  - term [ref=e871]: /source/manifest_ref/artifact_id
                  - definition [ref=e872]: sha256:f42083f9985afabcee9bb4320b727525f74ac5067162daa4b3be4109dd0bf051
                - generic [ref=e873]:
                  - term [ref=e874]: /source/manifest_ref/kind
                  - definition [ref=e875]: core.run_manifest
                - generic [ref=e876]:
                  - term [ref=e877]: /source/manifest_ref/media_type
                  - definition [ref=e878]: application/json
                - generic [ref=e879]:
                  - term [ref=e880]: /source/manifest_schema_name
                  - definition [ref=e881]: polisyos.core.RunManifest
                - generic [ref=e882]:
                  - term [ref=e883]: /source/manifest_schema_version
                  - definition [ref=e884]: 0.1.0
                - generic [ref=e885]:
                  - term [ref=e886]: /source/producer
                  - definition [ref=e887]: "null"
                - generic [ref=e888]:
                  - term [ref=e889]: /source/registry_bundle
                  - definition [ref=e890]: "[object:artifact_id,kind,media_type]"
                - generic [ref=e891]:
                  - term [ref=e892]: /source/registry_bundle/artifact_id
                  - definition [ref=e893]: sha256:32a37f444b0833ab853051f73b91a44ffc92c5eee4729640e33392fc575e456f
                - generic [ref=e894]:
                  - term [ref=e895]: /source/registry_bundle/kind
                  - definition [ref=e896]: core.registry_bundle
                - generic [ref=e897]:
                  - term [ref=e898]: /source/registry_bundle/media_type
                  - definition [ref=e899]: application/json
                - generic [ref=e900]:
                  - term [ref=e901]: /stableAddress
                  - definition [ref=e902]: /api/v1/runs/R_run_paper_empty_001/paper
                - generic [ref=e903]:
                  - term [ref=e904]: /stageTrace
                  - definition [ref=e905]: "[object:availability,owner_route,section_id,trace_ref]"
                - generic [ref=e906]:
                  - term [ref=e907]: /stageTrace/availability
                  - definition [ref=e908]: available
                - generic [ref=e909]:
                  - term [ref=e910]: /stageTrace/owner_route
                  - definition [ref=e911]: core RunManifest.trace_ref
                - generic [ref=e912]:
                  - term [ref=e913]: /stageTrace/section_id
                  - definition [ref=e914]: stage-trace
                - generic [ref=e915]:
                  - term [ref=e916]: /stageTrace/trace_ref
                  - definition [ref=e917]: "[object:artifact_id,kind,media_type]"
                - generic [ref=e918]:
                  - term [ref=e919]: /stageTrace/trace_ref/artifact_id
                  - definition [ref=e920]: sha256:b84dd8158412f8c2ce24e42a74c3ca6630abdb81cf2352818f7de7e50988a7e9
                - generic [ref=e921]:
                  - term [ref=e922]: /stageTrace/trace_ref/kind
                  - definition [ref=e923]: core.trace.jsonl
                - generic [ref=e924]:
                  - term [ref=e925]: /stageTrace/trace_ref/media_type
                  - definition [ref=e926]: application/jsonl
            - generic [ref=e928]:
              - generic [ref=e929]:
                - term [ref=e930]: Manifest schema
                - definition [ref=e931]: polisyos.core.RunManifest@0.1.0
              - generic [ref=e932]:
                - term [ref=e933]: Registry bundle
                - definition [ref=e934]: sha256:32a37f444b0833ab853051f73b91a44ffc92c5eee4729640e33392fc575e456f
              - generic [ref=e935]:
                - term [ref=e936]: Replay address
                - definition [ref=e937]: /api/v1/runs/R_run_paper_empty_001/paper?manifest_artifact_id=sha256%3Af42083f9985afabcee9bb4320b727525f74ac5067162daa4b3be4109dd0bf051&manifest_schema_version=0.1.0&paper_projection_hash=sha256%3A97f5ed0b652f169ab275acbe74527e4a6b365af7cfd5d72d0b977e00c30d1e3a&paper_projection_rule_version=policyos.runtime.run_paper.v1
  - region "Notifications"
  - status [ref=e938]
  - alert [ref=e939]
```

# Test source

```ts
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
  1350 |           href: link.href,
  1351 |           paperEligible: "true",
  1352 |           printedTarget: expect.stringContaining(link.href),
  1353 |         })),
  1354 |       );
  1355 |       const emptyPdf = await page.pdf({
  1356 |         preferCSSPageSize: true,
  1357 |         printBackground: true,
  1358 |       });
  1359 |       const emptyGeometry = await readPdfPageGeometry(emptyPdf);
  1360 |       expectEveryPdfPageToBeA4(emptyGeometry);
  1361 |       await testInfo.attach("run-paper-empty.pdf", {
  1362 |         body: emptyPdf,
  1363 |         contentType: "application/pdf",
  1364 |       });
  1365 |       await testInfo.attach("run-paper-empty-geometry.json", {
  1366 |         body: Buffer.from(JSON.stringify(emptyGeometry, null, 2)),
  1367 |         contentType: "application/json",
  1368 |       });
  1369 | 
  1370 |       const growth = await openRunPaper(
  1371 |         page,
  1372 |         fixtureMetadata.run_paper_growth_run_id,
  1373 |       );
  1374 |       await waitForRunPaperPdfReady(page);
  1375 |       expectAuthorityAbstainingRunPaper(growth.packet);
  1376 |       expect(growth.packet.artifact_links).toHaveLength(
  1377 |         empty.packet.artifact_links.length + 64,
  1378 |       );
  1379 |       expect(
  1380 |         growth.packet.artifact_links.filter(
  1381 |           (link) => link.artifact_ref.kind === "test.run_paper_growth_output",
  1382 |         ),
  1383 |       ).toHaveLength(64);
  1384 |       expect((await censusVisiblePrintEgress(page)).links).toEqual(
  1385 |         growth.packet.artifact_links.map((link) => ({
  1386 |           artifactId: link.artifact_ref.artifact_id,
  1387 |           href: link.href,
  1388 |           paperEligible: "true",
  1389 |           printedTarget: expect.stringContaining(link.href),
  1390 |         })),
  1391 |       );
  1392 |       const growthPdf = await page.pdf({
  1393 |         preferCSSPageSize: true,
  1394 |         printBackground: true,
  1395 |       });
  1396 |       const growthGeometry = await readPdfPageGeometry(growthPdf);
  1397 |       expectEveryPdfPageToBeA4(growthGeometry);
  1398 |       expect(growthGeometry.length).toBeGreaterThan(emptyGeometry.length);
  1399 |       await testInfo.attach("run-paper-growth.pdf", {
  1400 |         body: growthPdf,
  1401 |         contentType: "application/pdf",
  1402 |       });
  1403 |       await testInfo.attach("run-paper-growth-geometry.json", {
  1404 |         body: Buffer.from(JSON.stringify(growthGeometry, null, 2)),
  1405 |         contentType: "application/json",
  1406 |       });
  1407 |     });
  1408 | 
  1409 |     test("bounded identity A4 print", async ({ page }) => {
  1410 |       const identity = await openPrintSurface(page, {
  1411 |         path: `/runs/${fixtureMetadata.run_paper_empty_run_id}/report`,
  1412 |         readyTestId: "run-report-page",
  1413 |         selector: '[data-testid="run-paper-identity"]',
  1414 |       });
  1415 |       const bounds = await identity.boundingBox();
  1416 |       expect(bounds).not.toBeNull();
  1417 |       expect(bounds?.width).toBeGreaterThan(0);
  1418 |       expect(bounds?.height).toBeGreaterThan(0);
  1419 |       expect(bounds?.width).toBeLessThanOrEqual(794);
  1420 |       expect(bounds?.height).toBeLessThanOrEqual(1123);
> 1421 |       await expect(identity).toHaveScreenshot(
       |                              ^ Error: expect(locator).toHaveScreenshot(expected) failed
  1422 |         "run-report-identity-a4-print.png",
  1423 |         {
  1424 |           animations: "disabled",
  1425 |           caret: "hide",
  1426 |           maxDiffPixels: 100,
  1427 |         },
  1428 |       );
  1429 |     });
  1430 |   });
  1431 | 
  1432 |   test.describe("DS9 human decision gate", () => {
  1433 |     test("available pre-action gate retains readable hierarchy", async ({
  1434 |       page,
  1435 |     }) => {
  1436 |       const runId = fixtureMetadata.core_run_id;
  1437 |       const gate = bindHumanDecisionGateToRun(
  1438 |         availableHumanDecisionGate(),
  1439 |         runId,
  1440 |       );
  1441 |       const surface = await openHumanDecisionCase(page, runId, gate);
  1442 |       const request = gate.decision_request;
  1443 |       const mandate = gate.mandate;
  1444 |       expect(request).not.toBeNull();
  1445 |       expect(mandate).not.toBeNull();
  1446 |       if (!request || !mandate) {
  1447 |         throw new TypeError("DS9 available fixture lost its signed inputs");
  1448 |       }
  1449 | 
  1450 |       await expect(
  1451 |         surface
  1452 |           .getByText(request.delegation_contract_ref, { exact: true })
  1453 |           .first(),
  1454 |       ).toBeVisible();
  1455 |       await expect(
  1456 |         surface
  1457 |           .getByText(request.decision_rights_matrix_ref, { exact: true })
  1458 |           .first(),
  1459 |       ).toBeVisible();
  1460 |       for (const right of [
  1461 |         request.five_rights_requirements.right_decision,
  1462 |         request.five_rights_requirements.right_person,
  1463 |         request.five_rights_requirements.right_information,
  1464 |         request.five_rights_requirements.right_format_channel,
  1465 |         request.five_rights_requirements.right_time,
  1466 |       ]) {
  1467 |         await expect(
  1468 |           surface.getByText(right, { exact: true }).first(),
  1469 |         ).toBeVisible();
  1470 |       }
  1471 |       await expect(
  1472 |         surface.getByText(mandate.mandate_record_ref, { exact: true }).first(),
  1473 |       ).toBeVisible();
  1474 |       await expect(
  1475 |         surface
  1476 |           .getByText(gate.exposure.required_artifact_digests[1], {
  1477 |             exact: true,
  1478 |           })
  1479 |           .first(),
  1480 |       ).toBeVisible();
  1481 |       await expect(
  1482 |         surface
  1483 |           .getByText(gate.exposure.exposure_session_ref ?? "", {
  1484 |             exact: true,
  1485 |           })
  1486 |           .first(),
  1487 |       ).toBeVisible();
  1488 |       await expect(
  1489 |         surface.getByText(request.decidable_until, { exact: true }).first(),
  1490 |       ).toBeVisible();
  1491 | 
  1492 |       const appeal = surface.locator('a[href*="appeal_case_id"]');
  1493 |       expect(gate.contestability).not.toBeNull();
  1494 |       if (!gate.contestability) {
  1495 |         throw new TypeError("DS9 available fixture lost contestability");
  1496 |       }
  1497 |       await expect(appeal).toHaveAttribute("href", gate.contestability.href);
  1498 |       for (const id of [
  1499 |         "#human-decision-accountability",
  1500 |         "#human-decision-dissent",
  1501 |         "#human-decision-override",
  1502 |         "#human-decision-blocking",
  1503 |       ]) {
  1504 |         await expect(surface.locator(id)).toBeVisible();
  1505 |       }
  1506 |       for (const action of ["approve", "reject", "request_evidence"]) {
  1507 |         await expect(
  1508 |           surface.locator(`#human-decision-mode-${action}`),
  1509 |         ).toBeVisible();
  1510 |       }
  1511 |       await expect(surface).not.toContainText(
  1512 |         "DS9-HUMAN-DECISION-PERMISSION-REQUIRED",
  1513 |       );
  1514 |       await surface.locator("summary").click();
  1515 |       await expect(
  1516 |         surface.getByTestId("human-decision-fact").first(),
  1517 |       ).toBeVisible();
  1518 |       await waitForStableRender(surface);
  1519 |       await expect(surface).toHaveScreenshot(
  1520 |         "ds9-human-decision-gate-available.png",
  1521 |         {
```