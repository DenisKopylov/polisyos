# Source-led second review of E02 v2

## User request and boundary
User2026-11-01 12:20UTC, Sentinel_8aa6cb5ba17c8191b8a2e1d790c15f38:
<transcript_evidence>
«Поищии в интернете и в авторитених истгчниках по разработки пррограмного обеспеченния и построеннию архитектруи какие еще ошибки и корнер-кейси возможни в формулирвоанние таких крупних тз. Затемп давай проверим еще раз все пакети ТЗ и лейн-интеграицонние проверки относительно етих найдених в источниках ошибок и корнер-кейсов»
</transcript_evidence>
Research authoritative sources FIRST, consolidate bounded criteria, THEN audit every127 currentv2packet and12lane/38+4integration contracts against them. Previousreview is complete background, not proof this pass. Do not manufacture new defects or repeat alreadyfixedv1findings. No product edits/installs/native tests/external writes; independently computable stdlib examples allowed and clearly notproductexecution. Proposed nextspecedition onlyif verified changes are useful; preservev2immutable.

## Exact inputs
Cwd /workspace/scratch/91929078ca31.
P=e02_source_based_review/baseline/PolicyOS_E02_Review_and_Specs_v2.
Target P/00_Общее,01_Лейны,02_Пакеты,03_Интеграция,04_Трассировка. 127packets,606REQ613TEST,12lanes38sharedvariants+4stories159bindings. 282sourceIDs291occurrences425residual490remaining803preserve. The subfolder P/07_Техническое_review/baseline contains OLD v1 snapshots: NOT the current audit target. P/07 currentreview providespriorreasoning, notautomaticPASS.
R=e02_repository/policy-engine, commit20d9009be21097bfbdc38a546a15cc60213b8ace. Relevantactualcode onlywhenneededforcounterexample/feasibility. Read applicableAGENTS/CONTRIBUTING ifinspectingrepo. Source-basedreview concernsformulation/architecturalcontractcompleteness andrealcapabilityevidence, notanotherunbounded repositorybughunt.
Deliveredv2 ZIPSHA7f22b1737f67b20137ce57b95bc77b244c479d4c850e96aab3f3e518e68501ed; Libraryreference BASELINE_REFERENCE.json.

## Source phase
Primaryauthoritative sources, actual relevantfullsections, exactURL/version/locators/date/accesslimits. Distinguishstandardnormativecontent frominstitution'sguidance andourapplication. Paywalled/abstract-onlysources cannotbeclaimedreadinfull. No longcopiedpassages; shortparaphrase+owntechnicalcounterexample.
Each criterion: id,category,label,source_refs,source_proposition,applicability_trigger,concrete_corner_case,bad_spec_or_false_assurance,required_discriminating_evidence,scope_limits,tradeoffs. Source-orientedIDs canbeconsolidatedlaterwithoutlosingtraceability. Catalogshouldbeusable notencyclopedic; duplicatesmerged.
Avoiddogma: NASA'what nothow' means distinguishrequirement/design/rationale, NOTdelete user-requestedtechnicalsolutions. Atomicity concern isindependentacceptance/ownership ambiguity, notwordcount. Qualityscenarios needmeasurableconditions butdo notinventSLO/samplepower. Security/cost/tradeoffs applywherepropertyisclaimed. Genericguidance cannotaddnewsovereignsubsystems,allplatforms,fullCIperpacket,orunboundedproof.

## Later audit phase (do notstartuntilrootfreezescriteria)
Readfullassignedcurrentpacket solutions/tests and sharedcontracts, notkeywordsearchonly. Everypacketandsharedscenario hascompletecriteriondisposition: applicable-covered / applicable-gap / bounded-partial / not-applicable / unresolved. Each substantiveassessment citesexactREQ/TEST/section/sourceowner; notapplicable needsreason, notsilence. Groupedcriteria dispositionallowedifreasonreallyshared, machinecoverage mustremaincomplete. CoveredmeanstheSPECaddressesrisk, notproductPASS.
For a newfinding: sourcecriterion, exactcurrentv2proposition, realisticcounterexample satisfyingcurrentstatedpreconditions, differencefromalreadyknownlimits, impact/confidence, smallestcorrection/alternatives, affectedlocal/sharedtests, preservation/compatibility/owner, boundednextstep. Ifwrongimplementationcannotactuallypassthefullv2contract, don'tclaimgapfromoneisolatedtest. Checkrelatedgeneralrules/commonbindingfirst. Sourceguidancealoneisnotproofdefect.
Reviewwholelanecapability andcross-lanejoins: sameinputs/basis/versions/times/owners, actualhandoff/freshconsumer, independentlymeasuredproperty, conditionalexceptions/activation, sharedresources/failurestates, meaningfulpositiveandnegativepaths. Do notmultiplyonewitnessintoindependentconfirmations.
No changes duringinitialreview. Parenttriages,thenmayassignproposedrevisionseparately; originalsourceIDs/maps/protectedcontracts preserved. Currentv2alreadyhasimportantlimits andindependentoracles—recognizethem.
