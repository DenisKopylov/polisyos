# R975 addendum — correct the R940 B134 source anchors

This append-only note corrects the source-line claim in R940. The R940 and R932 records are unchanged. No product-source repair is warranted from this citation issue.

R940 said the R932 hnswlib v0.8.0 anchors were wrong and cited hnswalg.h lines 623–647 / 650–747 and bindings.cpp lines 216–224 / 864–873 for serialization, loading, and Python binding. Those are not the relevant line ranges in the lock-pinned package source.

The package identity is the PyPI hnswlib 0.8.0 sdist pinned in uv.lock at SHA-256 cb6d037eedebb34a7134e7dc78966441dfd04c9cf5ee93911be911ced951c44c. Its extracted hnswalg.h SHA-256 is 0fb2c1b1d3aae1ea959b536f96844f3f3ae6a2f32ce063f2c31f93d84a7e5c32, matching the full-file header hash in R932. The corresponding locked-source ranges are: writer 685–712, loadIndex 716–780, corruption preflight 754–770; bindings.cpp load wrapper 230–238 and Python load_index binding 943–947. R932 also records bindings.cpp hash 713332126d6cf1895677239853617667cd8a75f6e3de3ae4cb16af7f312c6ca2. Keep the GitHub tag locator separate from the PyPI lock identity unless their byte equality is independently demonstrated.

R944 then exercised the bounded native control against current source. The R943 and R948 frames both pin vector_memory.py at abffd306f3251de6e2ecc1003b6a80307f298e1f73707d99a4405ff64dafb5f9 and test_trn_02.py at bc16acefcd25b991b340f64dca49c00ed7623243dcb1d14bb94bc310a373f235. The R944 JUnit records PASS for test_truncated_native_index_refuses_and_preserves_generation and test_native_capacity_mismatch_refuses_after_load_and_preserves_generation, as well as the other bounded generation controls listed in the companion JSON. That supersedes R940's statement that native behavior was still UNRUN for this bounded control.

This does not make R944 globally green: its receipt has 118 passes and one V7 predictive-calibration failure, plus a separate Torch thread-profile failure. The bounded B134 result is PASS only for the executed controls; closure_ids=[] and independent G adjudication remain outstanding.

Evidence: R932 native source JSON 9dc211be5cc600cf38fbe90d9763fc7b682967b2756d3dfc18f5a9a3cb27cf03; R940 review JSON bb916d862a435c123cc825a16d01c68de17704783e3d5e5968b5eb28d31e6c85; R944 deciding receipt 1e8f17050acf2c1fc15ae3d41fd5deb5d640274fa560d51280528e0f0de2fdc3 and JUnit a8af464e4505a2bf1e1904accc07eb09acf79e72152398a3497c9e9f4af27e91.
