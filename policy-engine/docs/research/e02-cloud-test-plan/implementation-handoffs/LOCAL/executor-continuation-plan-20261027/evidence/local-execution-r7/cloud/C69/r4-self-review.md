# C69 r4 self-review delta

R4 corrects two issues from r3: the predictive V4/V7 exit requires neither completed N7 nor grounded causal N8; and fixtures defined inside the existing served-test module are not automatically injected into the new test module. The prompt explicitly reuses the existing gateway class and small test-local setup without editing a shared fixture or requiring credentials. The full source/pin/criterion admission from `self-review.md` remains the same.

Prompt SHA-256 `fd0e8fa42fc3631d98ceb1712b23396f9b7a9f76eaee4243e5121da3e692398a`; binding SHA-256 `5a3dca231471d4591a542591fb1e096c8bb8f74b79ef6b263374a138e27e9132`. Independent review has been requested. No Cloud dispatch, product tests, installs, canonical edits or Git index/ref writes occurred.
