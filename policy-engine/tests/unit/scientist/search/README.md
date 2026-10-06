# Scientist Search Compatibility Tests

This subtree contains historical search tests. New imports should target
`polisyos.scientist.methods.search` while this location remains as a test
compatibility bucket during Wave 4 closeout.

`test_adversarial_streaming.py` executes typed GDP and cost objectives through
initial and adaptive stress search, then reopens their CAS payloads. It also
checks scenario accounting independently of duplicate issue grouping/top-k,
partial and unknown outcomes, and retained full payloads during evaluation.
Plateau numerical/controller witnesses are under
`../methods/search/test_stopping_numerical_oracle.py`; current embedding
freshness witnesses are under
`../orchestration/engine/test_convergence_numerical_oracle.py`.
