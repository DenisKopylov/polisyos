# Correction to G’s ninth-wave B review

G’s published `76746fe…` review compared lossless JSON-envelope bytes with the receipt’s original native stdout bytes, then incorrectly requested a hash/source rebind. That demand is withdrawn. [Exact Git readback](B-journal-readback.json) decodes both `e02.lossless_utf8/v1` payloads and compares them byte-for-byte with the original committed stdout, not just a self-declared hash.

| Output | Envelope SHA-256 | Native stdout SHA-256 | Native bytes |
|---|---|---|---:|
| journal | `288d9f59feb51b4f807af25fcb300448aa3d3ce698808b864592b4a610f18822` | `d700695c86bd3d2a0a9cec8b3aa5d8075942a9551eca78c3a5cd0abaa62ce52d` | 1094 |
| control | `acdb8c12292a9bcf0abf0e02f1e2427c18b5df382cff7246f8f266a239d61ade` | `9f7c7ba6bd9369a7d2349454f399dd7f33e4b43920bac97767b2d33f7b9dd163` | 1102 |

The receipt’s instrument/test checkout `72965ae4d665db7d57ba0a2dbd7c050e5795492b`, tree `38bca96997cacfc24f985a1a74f74aa1018f8bbf`, and separately labelled product-source role `21dbeabe…` are different roles. Both have zero product-source delta from their cited f796 slice base; there is no loaded-module-origin inventory. Do not call the observer probe a qualified product-code execution.

Deliberate SIGKILL preserves four phases and one completed case with the journal, versus zero phases without it. This is a valid bounded crash-preservation result; it does not need terminal JUnit or a complete suite partition. Those would be required for a completed-suite claim. No input-integrity defect, source rebind or additional author rerun is required for this property. B74, write-scope carrier acceptance, and formal finding closure remain separate.
