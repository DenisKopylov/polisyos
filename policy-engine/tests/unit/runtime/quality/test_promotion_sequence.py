from __future__ import annotations

import base64
import hashlib
import json
import zlib
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from inspect import Parameter, signature
from pathlib import Path
from tempfile import TemporaryDirectory, mkdtemp
from types import SimpleNamespace
from typing import Any, get_type_hints
from uuid import uuid4

import pytest

import polisyos.runtime.quality.confidence_ledger as confidence_ledger_module
import polisyos.runtime.quality.generation_cycle as generation_cycle_module
import polisyos.runtime.quality.promotion_sequence as promotion_sequence_module
from polisyos.core import artifacts as core_artifacts
from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.contracts.c4_persisted_profiles import c4_profile
from polisyos.core.contracts.value_outer_set import DataTrust, ValueOuterSet
from polisyos.data_forge.read_api.catalog import build_slice0_fixture_catalog_graph
from polisyos.pdc import (
    ArtifactRef,
    AuthorityBoundary,
    AuthorityDerivationTrace,
    GyComparisonAdmission,
    PromotionObligationClass,
    PromotionObligationRecord,
    PromotionObligationStatus,
    PromotionRiskSpendRecord,
    SearchTerminalKind,
    build_gy_comparison_projection_plan,
    gy_content_hash,
    gy_recorded_content_hash,
    promotion_obligation_instance_id,
)
from polisyos.pdc._impl.layer2_design_search import (
    Layer2S6BlindSpotPostureInput,
    Layer2S7DelegationPostureInput,
    Layer2S8ValuePostureInput,
)
from polisyos.runtime.quality.confidence_ledger import (
    ConfidenceLedgerCheck,
    ConfidenceLedgerError,
    ConfidenceLedgerSession,
    ConfidenceRiskBudgetScope,
    OwnerCertificateEvidence,
    OwnerCertificateVerification,
    PredictableClaimSpec,
    project_n9_promotion_certificate,
    recompute_confidence_owner_evidence_hash,
    recompute_confidence_owner_projection_hash,
    validate_confidence_ledger_receipt,
)
from polisyos.runtime.quality.credal_reference import (
    CREDAL_REFERENCE_SCHEMA_VERSION,
    AdmissibleCompletion,
    CredalReference,
    CredalReferenceEdge,
)
from polisyos.runtime.quality.data_forge_binding import MeasurementRootProducer
from polisyos.runtime.quality.generation_cycle import (
    CandidateSummary,
    PromotionPortObservation,
    ValueCalibrationReceipt,
    ValueGateReceipt,
    ValueTransportReceipt,
    _apply_promotion_to_summaries,
)
from polisyos.runtime.quality.grounding_bind import (
    GroundingBindGate,
    GroundingDecisionCertificate,
    recompute_grounding_decision_content_hash,
    recompute_grounding_relation_content_hash,
)
from polisyos.runtime.quality.grounding_relation import GroundingRelationEngine
from polisyos.runtime.quality.open_world_risk import (
    OpenWorldRiskPromotionGate,
    PromotionRuntime,
)
from polisyos.runtime.quality.workspace.loop import load_workspace_fixture_manifest
from polisyos.runtime.quality.promotion_sequence import (
    CanonicalN9PromotionPort,
    CanonicalPromotionInput,
    CanonicalPromotionReceipt,
    LegacyPromotionStrangleReceipt,
    N9DesignProblemBinding,
    PromotionCertificateOffer,
    _gate_outcome_hash,
    recompute_authority_trace_hash,
    run_canonical_promotion_sequence,
    validate_canonical_promotion_receipt,
)

REPO_ROOT = Path(__file__).resolve().parents[4]

_ROUND1_V5_V2_RECEIPT_ZLIB_B64 = (
    "eNrtfXmPXMeR51d56PljbSy7mffRWgPj8XoE78iSIAn2zgrEQ57NGtbRroOHZX73jch8Z3VVsyWSsqhpYcbsei9fnnH8IjIy8oeL"
    "XXieVq59mba7xWZ9cX1xu1kuwpvN7qr+0ca0W9ys2+B26Wrp3qQtb2/eXK1te7vdrDZ7+Ojqpbx4crF5tU5bfPhfKexLVT+8R+XH"
    "tV295NBGVxwe+2VatX6xjov1DbZ09GYRoTGoJivtaXI5KZOFoNFxRnXyytnMtKAW6uw/CZv1Pq337XO3ew4f7547JtU1Z8FnzYgk"
    "8I9KPCvJfaAsWi4Scd4bpkTwBkqZZCmJGooZkpwP3mqaoYHVJqZlu7tNod2mfHG9PiyXY7Pnp2h7WO8Xq3Q1H9rVPu32Vy/pxdsn"
    "F8HB+KPbp3Z3WK3c9g3OxPiwTML4c42jPT1K9p7/YcVvwhKaXMf0+uKaPLm4SbCADpeuDc/dep2WuCKiLmyd9tdvYPSbbYLyV+zJ"
    "xcvNooWxLVbQWXxEoZLt5lCWuN3t3f6ww/EctlscwEu3hPHNimwO25CwyE1u82KbXrnlclYiLna3m92iUieOPW5etR7fzivqO2Xl"
    "k6P2rvfbQ4KuuuUhjX2qP7fJxTcX/cuYwgJXtL3Zuoi9er64eT68LYQw0Nh7/jfU6peb8AII6eL6+2fQ87TdL/Iixda/wcW/zm65"
    "g87nLdAAtL5Nu+S2ATuFfWvLigylljA1w5QMT/92cFsHZLlOreu4/GK9WSeow0WkYbdduGWdrLr4wyStN3sY9t8OsDCxECKQd9qm"
    "1251u0wjZ7wdpyikxe3+fjHS88iU2pAQr2odN0j3XUXIM0/ewR0JP6vVINfiEi1WhyW+36yXuLi7tASBBHO6Svvnm9jmv61LNYed"
    "W14t1hlGtA7As4t4BSNfR7eN/4rtdsXr51j/fuuQWL9/57ewkosIFAhLGY6m9HazgJXsJ2xzgPmEFsqUbdMtru9677pVWuBsQ0Gg"
    "99cXZXmBDa+/p1cEGjjc3k5+hc1mC6sOo0ZKuniVltkBQzygI24HgugW33U0OD4YC6fX0JM18CawPzS82e4rQQDN+G4NgQNvU135"
    "8sfFYb3Yo8SDpXIwdYddGeR+gb2uL59clMegSm4vrmEc/W9Yvv3idllKlserBdDIBmjJ3aReGK/c6zvPBvXW5iVMCMoDEAfuAOu4"
    "XezfdCyMHbosLV0/fdr38tVmu4xtlftAfTCbc4YX7/kfUurtJqAAZ4Qp+Dlf7om07GUAku5mCSNskV9af4g3CSZn14/21SLuob7v"
    "CVDAW5w7t97h0szYsK81Ag8HnPITAy1s9Wq1rQx1osBpDfQBpmTa5x2sejfnw+N+gaYlhyH1lF1manzfSYFhwEcMkNY3IApHEuzl"
    "W7t3W5xfpI7KCMvFatEtDnSrcMfbOc2fmuhb4B+oNoM+Aoi0bzuC3/gd8jLAgbav4Q4LzemOknH0hzVShQOOfdMOUqHvFDSGkr4F"
    "Geq2bRHS8PwH6OsCWBmew4T0vf9Frf7H0asIISrHIKsU+YGjCw400kg8/rBY4sy+aOuIoRetT7mgiA84xGn1Lu8LKXyo2k8uZy8c"
    "JgiqRzWdYAkFqz1IQ99bR6ecxweder5hpVTrVcjRSR0c5Vl4cxbJHhfMmUZrbUo+OhIzoS4HxQOl0kbOvFFaqhiMI0kTYmIqRkbt"
    "Hy7sokDD+uRlgXi74UWbloubBTDhFBZs07LXuABtiswoALN1+82qHxSpv1wmiTkrFBgRLLICz29oe2IW6sOWGx6lDZ4qI2OKof/g"
    "tOVyVJgKbYOlBibGeeJEsj5ElSTjJqRohYNZIp5Lq3Mkicau8vT6to7so7UC5FyRT9srtRfw6JoHzqJSiVDJTBJyVvKoE0dFdbKW"
    "c6q0IkoS44MxCTqouI06UEegP9nmZBlYaZrbMKu6o2GUehdfsE62Xy7RxvmCDz9ROHyhxi4QCTQEFKesgXYiUSEYRaWmNrIkjVCa"
    "U5kST46CfZid4k4YEhIaldJwrP2vf/6mrx5kDHLkDgzXtmoE/KsjoQLKzhPRswnIxaI/XDyM9E5QbgfP2gRgocdk38Ow2//48qt/"
    "a7/6+o/f/P67r765vt4DfILPFyCXUBWVqall/vrVN1/87/bbL7767kypL/74f9s/ffndH7/5yx+//O5PX33Z/vn3X8+KFiFbSsP8"
    "tF9/9cWf/vCfpcKx5G652V/fLDceYHT50g3lp+0fl3g2DrBK8lTX/J3Du0bZAwbmqijdhwz1zhcPHvb8yx83BXe/vW86pqWLum+n"
    "Fl1nrg2UNViESJm9WTyIR5QVYN/sOzdOEaNvYb63G4+YfAdqYJn2WBQ/RCC03OxAxmw8iFTX2w9gUq4AdSz8YomAu5ZB7FucBCBT"
    "q04pz5a8XSqUUbvFDsRUQFttvWkPa8CCiHtBfgFqB6G6bN3rBYIqoGYY92YLM36D3yBsW6aXxTnRwbdX8ElBWajzcYoLelrAAKCe"
    "NLa2R1qC+tZHA8Cnswc/TH5XjjwzxBHA90+GuQW75HYDFmMz+7RZ7Joy2ZfjNL1EtBqKfp6V7YAlrvPbJ3e7dGp67+lPXxx7MPli"
    "2npfBMdbjSyw4ZLbr1CfpJwRW5/syunJvrc7+MnT8gl2aPyqebXYP2/2z1OdpgbYoanL3HQrO+1xgcrXFwVLD/QAD+5KGaSmmdYH"
    "CwCwKPbz5JDuIa17RtX1tCPmXbPfNK7p62j+isjtzwjcvim4rano69TAzo7kZGfv45F7ett/dtTfsZLmC9X09Ux7139YRjwXoSf7"
    "d4rr7+nX//nuD583YbvZ7S4B5gILTb5Eavn2998ddaizmYc6a4nDeuf2LXoJ2wVA8fWbYhCd6uD9Iuierq43TV+66amrwc/g1wps"
    "t10z1tvATL8EcXqH7043nXr/YP+oSuu4CIPceluE9WL3AlYbdP+2etiXe9fJhM5/gD4RQqFN+H7RgY2wWd1u1ql4GOsn33yH2H4H"
    "4jGWDwhhHSgef46+28GehUmHfw+rwUGLi4XG6h6RePd9UUI48XebXW2Ahzfbo6bpvGn6UZpGK/Sf0iwuA1rz683LtPyndKFae/+M"
    "pvdvbgEix9VHbhsYY7/Zu7KhM9Sq0YG2f75YD4xRAdGaonW26jcd5s7wV50nvBYC6FX4tuO4mUN84teZSsk2u9Vi+eaEsJzaMyh1"
    "i0ipEn+C9MuUTeH+II6mTqV+al6kEy39o1b6j6GK6s0vaPHimpEfY90NVnbepvT3EWGOagUUd+zm57q4BnqYuUvwwq3D88LvM0/y"
    "uCl0tnwFqd2eRRo2eWpztdTEHXGijuuTQzq2AjrEfd3P1az+09Z1oIr67GWkORslqcuWxCxZDsZlDoYtl9GTFGXggigtQmbGiJCc"
    "UYlJ4atfrN+KqRNZkHVtezpRXT/GWUAP3zaNn99xTHbbOGO/53tkP6fjoLfZ25XbI43VHkBvl2ky6mfFT47bzHG0WOrve5wuUmTq"
    "JNFMJh8Tqw33X50c2vEXQVsYTbZZWcJ9MNTghnKijiRjJIE5MC4q7xL1RDHvpy3c51i6W+ihln7f/fMI4IRLq8VNhk08hHH65g3f"
    "fX+mgQeXbPeHujl4XBzl5wrxF4jCYtmA2Ng/d+s2g8QcrMpxs6bfRxq4F3fRcWOz7PNA1aW1uuWDkHoQPuGGw+qu4ybn0eTtR33v"
    "/A3TtjnsQQekujP3/bB6w9bMJYYGgI29+Htd4H7vfPLg1kHZIrsn2qT8Ll26dPBjc1NMXlD8l6OVjlj1xRq4Hf2QZXc4oq3acTXy"
    "+0M8tmi/X4Hw68MOQG/VLYPKfj/WAXz8fXX+/iLcgG7XbnK3rXZJ1CXwC/rhVAu4HmDv7hboDuZ/f9hWewWt2eVyfHRR902yWyxH"
    "Yx6E0mFb7e6jFyCaDlvXGf/zHRt1/fRpfV+szJsb0OOVnsrinf5gUqzowVsXsGCGehZnW+mLlZ6uy2b4EjADmuzhZK9qoR4aQFEM"
    "bIGpAch0ovhQCHu0PKAB2I6MGYE01rvpthgQ6naBDkfEYIcVQqHNq95kgUdQ3WKNLjtk/8Nt7+bEt/x0xcPn1VYffhaGQILsbPi+"
    "/bJXd+I5rnK3Y4a7gFB1vLntujAN7dm9gUGu2vhmDfgs7Hr5MUY/jMjmBreWtqnurd15P9k0HAJ8Lr5VTSGyJoPZh36KphdqzdKt"
    "09XFfAsPUKpbIu0BUEVS1i3A5Z6UJqQ8eToIyW4VNazi+HqyQ9JuFzfP90Xrbhevp8XrC4wsOQC5jFs+OESQvLOi9dGpslNSqp3o"
    "dmYmXQhLgCJV590gOyKuuV1Ux8ewHbvdoEjvZNIQglSWsoax9Bu9tU34YtrULGpoKFHYcFrOvQTmLj4dF0YX5i0olZfF2Tx0uWsy"
    "vU5beJKKW6wrBmtX9pnqvHb9XxUz54eLkT46/TYtC/I3vLi7efx20u7mdqaeQJVAzQM2nEamAX27ajv0tI9BWcURPNJk92aIhXqR"
    "YB1Wt6jdrqvNVYTcq+foKwEeuIH3+HDbJheew6PNokTAIGPu9x1HBeSxrVvDUCh2soiVXnbhgt1UfX60Q94LrnullWr7Yn102FFE"
    "2FFl1XaYTEJHqgXvDEpCXxLzHSHX5f/+35Q04yGVgnVa8XF8x6cwd5vtdC0wJm6YjXUqaGwCZ0dxV+a7iwDs/+6jIGvI4FBi/Kya"
    "txn9bd9f9L7btgMbbe8zBoKeRWteFHJ40yIGO+yG7yc4KgLA3LxZdY7xbhqHvhaLfY+4bb0AEBbaDtyVqMBBkfbMjGx8WA4Qv1+N"
    "nxim+mx0kLUvFsUj3SnZVfUs3wnbG7l2mI6Jl631oFmHIJqCtCqH9DESc5k0bhn3sPdehTYojkFlndYIuinCqOkbuyyNNX3XrwqG"
    "MW3l1InMrw8qI7Zztkf2McA+pchlx6sD5fy9yj/ke5A78bCcfdM/Q56rMZa7ADVvF5sTHw37JCXQF8nxsB7Q+IkODQUrLE77TYtB"
    "jHV3fihV3wxhIQjOE84k8DuiLxj/tHT/+kMLEuRcxBG9coGfMHHoKWqPJ3J3R9GMJXCkjIxtHQu/W8bOv+wWfZxLtCCWwH/rtOtD"
    "Wm63i3VY3M7CgNAjBYy1n8KnslOT6sbQ7eQFdBxjz6YQrodWgybr3wAYwei/stQDHewQqsGjIh2qpP2v2tR6AyywKsGIIDon39Z9"
    "8CJe0HhqXyVsqT2pvCbYZnxYJ6afZdcJrgF7VClTyGPQ8c9+JMP+cDGYjlBT2QE9zcCmGVe7KR1rOja9uniU8r90Kf+230wu2z7r"
    "l5sw3QGyV2Pfdggg1qGLMlo6xKbj6pawQ5jnVQ/2KtY4HsoQnXgxRSR3huTiy8VuA/QxGdLb3t1RrCpY2YKea5jvmdV6dvzJhIMA"
    "EeZF9VWXKvoHwDNrC3YlMC+6Ry6HYT+bx3gBZwzR6mX7vIag3ZT4gjrZxRcwmrzT4yVdbJpoRx07hOxWuX0jLodHl1WiX8OzbtKu"
    "D+5ytVuly0q6lxjhfdkfK4BlqDpxk0v83+awH8yysRNHDgjHQjDOUhVyEPA/WuUYOIN/qMs+82wdU44nHokkytqYvRWMEZsyTyTL"
    "+ZmOUwHqg3SvivWiD1OeGI11FYGzO3IZON75XYeyL+6NSyg0gU28We8dxorfDL25edO+covdbLNgB1/tusDZ3lVfl6b61etSIP/u"
    "CiPHcIVmwvKqr+zq636Nvho6UfexC5vswapCGQkmJpi4X9pmsb497JsSp9gM7uq6vZ9eA3M00Jll3KF97BcRWOdqysoTNI/7m90u"
    "Tme4pxUebgiDuxDGAxq1e7qbTVtvU1b786ZDBlUITkvNR987w/52cGjRjKKh7XkEi7QD67R3C/zL2OLTYYnuNnzaNe2ykNZZFQwT"
    "WnBnPWFUmOxdZpYwQxLjzAkTrNQyCO+pUN7KKGgwSRXv22KNhxNCFxB2ph0vnOYSPjbUkeiCyopZH1ymRmlvaaCM8mCtopxr4IyY"
    "nKfeaM8EtYH5IdS68nyn0jvzewXrX8htutve96rQaT9akgVxibIYNQbfWaYNVzpELpMniQJ3piAdYVpbBYMmVjvJrHIhKM+cvzja"
    "0u85o+ybTfli3YHr9+CLY8q4c6LlL9jA59DkN12g+IQ5vjQdauiCyCd84XYN6KkGuxwHT9EpjvhgUdO/Dtbq1vihjBUlV0DnmjqZ"
    "tdBJJkZ8Vhz4TUvLFVChjEEnZqIknBNgAGs1DTx7bTRlnxZjEU0t9Um46CIHjQfDDlxrogMhXDuajWbRZyKpzTBemrlSCWZDxCSZ"
    "zvocY3UBSzPGmsKdfwpz/WXKWU+aoT/jI4x+w3iybskaXLLG3WxTuo/R3jtm/1eiw7rgtwcympCKUuE5iSy5LE20INWpdIoSq2LM"
    "IcioqaKawEPQYoIFIDhttUhKCR0/LUbTOXJlo5KcWOeAmTJnyYBKtsbbRKOQhhFiaczQpogwL4HExBkJWmujzDlGA+vPrebQ7hSO"
    "/vEsV3wxe0DHYGw9vWu0Pe2NNjED6wj2dlf/tetc+x3jfS66WM1aoBni3fbPAdPe1GjOW7QYd0XToWEByu2zBj4ECIxbOBjVBxZs"
    "M7OFy84JAMnf4NjS78aOdDukvz3JtT/ZmPh1sGlPMQ/lU2oT58AjJGaWpfI0mWxy1sl7o6TKhidjolLGSc6BnrmQLANBBxs1gfef"
    "Fp9KY5mXFtRfBlHjJaYDUBK4M3AeqafwCHBlopSCmccBZArCVIK+BdCIwZNzfBo2h9tljVOYKEXZTp6PDFpmCbp3yGBfL6qnYwie"
    "Ovn2pynLb+uZaHjwNajBr3wXKbdZX008Vf1R9Ak/d/u6xRuxvrku7Ftx6ZeyOVtp04+16QIpep4ObrsFcQT24H5T6gKWHmi4Womf"
    "NV0/LndgPkIVYAMjYQ9ioUEv6U+3D09P6i+Lcaek8kDetcyKkBVNBC1FGgT1kZpAnaHEi8Cl9M74QFQgRnCbolYSaJ4rGo2hjH9a"
    "vMtlhu5zAKdGg4jSMNQcCGMmJ+2BT6PQJILhGAXReMrLpWy8BkvHexBhip3j3e5gw9x/8qLFQ9qL5eroIMN7Mu/n/3n5H81YM3pD"
    "0L/f9Fvdo069ryCyxWFd4lI/a/7wOWsw8KfpWWOIPC/BqmvUw5Xv5oeim3Eqft2MNazvg21EoFkdJI1EWJYBtQGhR8aDcmAKMsa9"
    "4lJzbzKjAvRhpCoRMKrQPyGcUOnTYqtsAaMbz8ASVAaAKvVSOUW448EDL4EVTHlKnGSAAkYChBUChhtsJl6JLPg5tppT24y9MD63"
    "nMztA/nqcacPaDfOQ+I6QNqeONs86wFunrQnQg8HrvzD5//ezBLNFJMSObD/6hK/qvw4wODi8nSgyNaXY+RiA2Nd3Z5EsOdPU/86"
    "IOodyngoY2pNMxNcZ0+Y884BZvOGOQOCHhg24/FdJWC+bA7SyqRoBpPSE5mizwFY7VNjTAcySIDaA7zKBFjJoOWZS9KFmAXJlkiv"
    "gF2NpFyYIEAiUesFi6DZgT/P2pTTUwpHPpz5q4EbMRpyfuypngydrhiWeShSvXOK4qr3g548YHHH0zPpJqDLNSLE7oTwCCyvm7Gq"
    "plYFHJkxhw+ew+rPYLrFqunSkzU4BDCHkVHxsFhJJ1E69llToraauEkVjxb+RpWKy4lzM1Gmgx4+zdtDpy5Lnde9GSZBlOJWVHYA"
    "a5SllDkG5E2ZItp4EM2a55yJSIBwgk/JRgLwRlEBRA6C+Fg0PGDlpzt8J9KPIE1uDzWm7SIvXmO2FJyRyQr1WUmOK+ui+CbeiTLR"
    "uHHthgBbDH10IaRuabtd1npGaDyz8+TufudmjPC+50jOx5vpt5+gyD1i7AfKWzAZstdBKOqcgpkATG2VZJGjF1lxbgwBwCOD9Yxh"
    "EcVi8D4CCuJJuaw+LXlrRfbBmxiM8JElxT1XSlnFlJfEWgo0IoUNQDOaasJk5iwkpUDwwqTAZ+fk7Tyk4R2bUR/JN1DycQG6AbO+"
    "k3ZXfx679c1ms/+6Cx646qII2gwEBfS1704s3Osd+MPvv730Dn1yzVG1TR+U0KTXwMG7J40/7JsvzShL0T3wBuDRsIP+tENYl10m"
    "xQbDGSqaOnQuAzBovrSfNcXj/xWmU/s2TUT/gO4GS6iLjsMFaQYubdD39+s2feak91C2Nwj5Fdg+RAHSoMpq5ZXxADFoiAR3lAhw"
    "KHd4JsMDJ2RmtHMODAcHLFHS3XxCbG/AwvNSO+uCDhodgYxamTMLOSSmYezeRtAXwijBnUsOEFmQIXEpqRLBnmP7klPsXfz+S0NW"
    "2OmPAalq50FUbIAa28N6iMH/GaBV1Fwo4UHdCxkTVZRIC/QmlPMc1LyS0uWUNUmCESBix3wUmTmJyoB4px8ErbrVvoup7iYePIJW"
    "3anWGpIV2xLMFFKJCf10QNV7z/GnCKq6NX8wmqIgM6PVJGPEgZMM1ilFl7IUJAD21C5IB1a+oYQEmMaIdl4kEaw6FbS1n1joQfA2"
    "yJyCliBeKW4zOSMEVRH+UtGBghEcALe0QihA2EAaFoQsJZwJ6HY861bCqOjVkDB1KmBnx/8+SOhb2QVl/cZoTcN79UV5+K36N2zr"
    "W2jq6xom+yfcyZiFwqk+OripPJnidXPn4OHp0IP5scIThwaPjwTeiX2fHen7lTiOjtf+oaznvfMxOG8BukuaJGU28AgoHtgvkRgY"
    "EZEBkkmJMcM4UTyr4OEF5TYK8YmxXmRUQm0mMQOgXPBEFDPW+WSJMBIkT1Y5cbRxmMnZMcIxRAhYMUmNR/vPbpT87bBAM3JxWD1o"
    "n/PHcR2m6bnq3ai7q6NcyVczrD+Lqds0LxebZQmim/QQEclA/5f9uddmTHSMmyhdMt5fb+DpfMkeyi4KGCAwJwKRStIskgC6cDSI"
    "CIIbVFdOQhGumM7chhh5UCZqowMRlAG9m0+LXViiEnQR95ajHcDA0EmMW5o90/AKRo5MkoKTCrgneeAS+FcBygku+iDOsct6s125"
    "7gTUREnp4VDS7KzuR1JWLbR37mzbVFXppuvV5ARxt9nY667jY2u1nrJxclqH3TmPPD9yfHSq+Pjk8Eyh/Tq4cUoRD+XF5IGnGLEC"
    "cJOiTGhFjGQRt7yNQZ8bWOLEc00108pZDVgygTGrIwHOCvwT2+PXImiXvQe2A97DbQwio4jAkaCQszPJ6+CzYDIQnY22nGQTs/AC"
    "FDeJTJ1VXZhtC1NgFqw0OyixIe387Sz5k7sFvRbKafHiQ+uuF/gJe5InaGfa8IQSjrRb4ban4ymupp5LR/2F57FXyJuf1Ri7Ie6t"
    "pCoByxE1XCwG5BBKMwyohgXA42Ki4sD6+n66PhzmqD26RuKXphfnK/5AXgTbVTkenFDMWcc1nscAWKWBCU0w0iuCh4ccgEYFSDPJ"
    "FCUDbmIRzGLq8icW0yojyBUqARFTD0zJaUzRgl7khHMVMFERB1M+cTBgmQEzNSlruIBvsoQBp7P+8N4JNtGJx2eeP6I6NDXkbdd2"
    "p3yHmz7uPaeB2/zfdg8ve6Ouqke/wd39TkeeVoQnDmjfOYB9fGZ6fjz6+PjzsbVnjnTn4xGRCbMPXteHwl+mnZc5AuVLS5k2iZJI"
    "jAMtI2RQlgJ3h+xFYNRwydETDqVAW+WsswyfGJtbQzxVTFlBs8sAIqhWCfQs98DVgWqtY05gTTIhnE3MU5OZ15k5DHqiIT/Y/42B"
    "nezEucT32/IqkaL7pwe8qAYP9KbZacThSOywXYUJW/udpstyCvvJGJv+pOmPxl6OE9rUADJgy0u8NgtZoXjA+zj2ooj7xvuY9fEs"
    "8cfeYBrSMQ6q/udisWFe2um8/Bh9SgG2ReA0FUHTgKrRRkVLI9CcBP2ilUgUCJ6A4vEqGC2oFzkbZzOF3zp9aqccqSUaLE2GrXjG"
    "MgBXB1wHGFbnwJOzEf3kCmSKBAUqA6cJJErUCkCFp7/4w1hXAylO8jWPZDmLMf98qGxydqRO5XhyqyTdLhkrE3Zi1+9YDc8/qwAW"
    "DEgAtIvd87TrNfZliU1ZH+WOPrfjO0j+HISgUujkUoZ1ssaHQGMEOU+AFolnhABZZpGdStZ7KMwCsYQkITQr1xT+4g6NfRj58M7F"
    "/5eHr9qPUcXvvyCfUsQf9NxRaSXYsiq6ZIiwgDJADhBNNHSE2cjBGJYcBIUNTmnjuHe4O5+Fc+6/jYQY3MKFpvCepZ9JQLhkY4iO"
    "CS4cpyC1ZcqOJ+Nz9ioSxY2WPCVhgg42cBJsBkvRG4rR4Tbp/84C4sGL9mPyJLz/enxKJ2AUUZnQxHkCMQemSCLGUqqM09qDecJj"
    "lIYww5W0nHk8xw3WCldJOzBlfM1sNA9lqDnS55ECXYxAd/fg+IieyZ5eKutPh57LUvIYe/phYk8fo08+RvRJuYzrZSo5H7/+TenK"
    "5IziPxoMI8SrGEuijuHu1N82/+t3TRled4dN7BI+N7PjVc00lVvzP5shq3OzQ/uzPP0N+m/Ra/s/ds3vRfM7UHHbBnMtNV8z+9ur"
    "5o+Yjbqp/AP1l9lsFuvi9i1WbPMlpZP4rMsuPmvMgVTM1Onx6uIzhnHm5cbt4d02NZjZbuneXFY1+PbJxd2VqFLyznqgVLks7/pF"
    "SZF5ETTYMJpYmQGtZIG7iJQaL0FyahqDFZlwLbglkfKkAkfEw6gDwUUuTrX+PLnu8spJ2wnT/F4PiJGYrJlkTEcDHcBTvpL7ZAEX"
    "ah2FFCGKFBjVRjjQD/CHMNZS5q0MMYjzzc6vho3ecOlpMJjK2vGgYUxM6JCkIsYnTx2FcqCDLNQbBJGEGKqZMJrm4N3JZnpFeDzA"
    "7iqFPmBRGS48iZEbxTReLCBADwVnElC95zrTnJjnIUFrzLsQE5iS2nkYITXayJNNP/Q++F7tnwg0pBezlFs9ApkmfZtdRzlNmDfT"
    "iaPTYZtuN0WU9Hsfba9Fhz5d1rtdL8cy18NeUgbNF2myQiaY+6REtFI70KGZu2wUp1Y4AAIwhxlmMwuaUlAsC60T05jqperK2SXH"
    "7U/d7HmXO2U+H4ft7WZ3PH2D66v2pN70UR3cfbD0NZTPAEloApGHZoGg0XEg8uSVs5lpUYyiWs3ZBGmcBZ/x8gPi8eJDnhWwEGCc"
    "aLlIxHlvmBIgPPH4fLKURA3FDAHQE7wFAu8vPp6myO0vLB0ebMd0pD8tfeCTnk6PKukXo6ulm5mad7Fmxu9ca/FnkGG1qe7Wjvm1"
    "txbsVIBqmRCdStYd72TIXDNllbKO48WnzgGU1V5gWFKiwoYEKBaAA7SHt+l1cgPz/Z0WGpf4rh8OF5kK6L3CU+IsR4CJmGTfKOUF"
    "WNYxe2K5TAF0oiE56UCSBWEDSEUYZgQ5anE2Gi+iIACKqcY7QhgJ1IMxS6IVKQIKBqHMogYSgTIOBBaQIws6ggjVSfpIUO4WKVuE"
    "+UcX8ZOmPrRY/7ll+VF7s+FIMHqY4i5FpDKgJQdWUUAejUy4GIOBBlMw1sgIwiHi+R1jgqWApVzk1Q2Al8Ft35xL82OEkGgJ2QBr"
    "kKGZZIFsDBgpygWtMc2NNoYR6ozgnhKePEM3J2GROk86Ji7ZZc+KIyB+YrVF2orGMaezcprQUPYphLXROhsTARSdJLNSyOzB1IPV"
    "ZzzbKNnF9Jb4IefrO42UESjXVXynITL5YLjy6QEmy1375z2hdwHHdyjvw1oieHFQCof5dVnlNEA1ZWsOkNLxlJcl5293VmD2KZiM"
    "mARzSCM6vFiMPo3eVl3jLRP12sFiRKxrwmH8Td/2Zih6M1ZY4QXS1uwY53gxTD3ZsJvGXPTv+uiochZ8nPThnpky9WM3u4MORwSL"
    "Z2IyHg6hnDgFosFE5pRAItacm4gXmTAO0pEnYyNwBrBLFlCKWgpCIL3DzjsmzHuMuFMkedbIO2syfnx6fG8T7pEe76HH7BUHpJaS"
    "SUB2SSSQxhaktVJKgzpIGpU3CSUPoJNKuoiJEC1me4gIGS7uXKf3ztFPSh/NwdyvNKuIHldE8C6U6QfTuq4ImhwnXVI3m02v32GG"
    "DgVJf7VKN64dzPWSEQUl8q6zjze5PMNPm/JpSU3b1LkFwx9xZEkUgV6LemxpV+OugEvg+2qGY2qWXZf0AYiucXhecbJrXBbsqtpg"
    "vbugXincdfOX6H4oCff7LrSTLpQ76qZO2knO+un1VUNLXZ7q03qeKsw85jOxQQhvFRNZKA3Y1xEQB9ESIfHMLYAAq6QX2jOQngTQ"
    "hxEZNFc647HofeIf3sad5kI/VcP5Y3kzq/hEDx9mTg8fjkf5HmpTP5q2j6bte5q2P69pkBfLblwxZXdY7jHbP0z7DgizhgweFz7q"
    "TvZCKB5cShTIxwWweh1GOaWYmM1ae04Jk54xtMSk8mAIJ0kx8jqD7fizWSofWD0WS/1sf6MhmilFCHKF8R6ewd8xSyqtATMaWAuj"
    "rnW2sH4AzTSwHfMezErnVPShbJWiqiwWVVW43W21vS6oRuTLGpqIQ8CgRrxPvhT+mD0br9r6qaL+Z2WmeuNalXxrW073jXcKTDN4"
    "PF2bdmqLTm6HHZMojPbk0w4TPu19DoZ57okznGmuRE6Oe0UCcKqA5zlLIjQFDQvSkNLAMPSeRgDeFOOcA3GTzmaoNm3xWpr9ZE82"
    "4uUJHgxMA7zDSEgcls1qF/AYgwLKBzbMIRHthAD0GQGS4q5sIHiBbDjaCP3ZTfN6l8RM4ExqBwA0Hp/5EVb8cCjo3Ut3x94C9Nkx"
    "R9Uu72uNlfe1v3M6O0txl9P6sRPTz/H3rHBp4HK92U8S8fb3ddTGp5tIpY5xwS8/PLWWQwmvoNrNq1PLBOu879bgY0qjj68tJzQO"
    "KnKxXpwYCMGEoEE6Tb2kBmQQV8okPM3mtXYwHq2lpglmjwSB3BhVlAQwEvUZtKS4wyBH1StkYi8Nh3UgUjABvaSSwCCE4Zg1CA+7"
    "e0UzJxagvYJyJsfMCAAxU/TfxzDjB8UNYgtvYgJb7PV9Jv59G9RnTPj3cAq8h/nfjR1oqtwldCdz2bBck4jobt6ablavm1NfVRQ9"
    "uSSpkyrHDNJd7jOa2+Mk1io6dh5k15G/4jzHWUqBDTg32iTjvGPKGoRV1GGoPUgElTTVRlHQqyQD/I8avfbRsEyBcwa30/kWiHNA"
    "eUIysDsJofD/IgamvTMyR7zqW3tPQuZ4OpRKY5ME+0CYxBw3VJZEYO8CMQAoCVNR+azwtDU2aQg+ysFrMC+ENNFrDlYssJcAHqQy"
    "cq0VI4yBaCt+wAegKvZgVPW+HfqVoSpUDQinioooTs/pZvWgF+/4RI8xlQZRKagBAcqjixJ0laTeglGZjCXWaqFBK+jowQogQkXM"
    "LiSoYpJhHlVS5N69mAqG5YSjwhGZ4B/BE9OJgdaREaSphcXUgoDqsA50hwK7IwI5oy/Zcu/gg9OY6sO7k0+Ap7Opf36S93mCo+5f"
    "s18KihoH9G4QNSn7QTHUB6DOuxjq1Eo9CEq9vwj6ZUApRYPOQgEs8jFIDY88TC6oDscZmP6C4NaPAbUkMXcywFhllTMBxpxATQn2"
    "DijlYSFg9IRybiUJCrqHPlAXFAAqkQ2n2YNgDJiWOimXHKg+6VOEqlOKxD5CqfeCUveJrXdDqvu+/qdDK0poEICmtKZgNwFjGUBa"
    "FqwbmU3kzkoJyjMEF2Q0iVKdc1TURcQ+uEvM3g2tDAUd7L1mJmSdJCOOZwpkb2N2KUeplMO9JU7xvIYFYyn5HFj0hCjHSJIPgFbA"
    "u8BfIBkywAIwBrnIChACtwkVoQE5lw30gXGAjFACjEdgTLzAEVOba1djoesmTvFdPfqIHn1Ejz6iRx/Ro4/o0Uf06CN69BF9MB/R"
    "o6Pk0VHy6Ch5dJQ8OkoeHSWPjpJHR8kHdpQ8mx1m+Xjukg8X//sYsPurCdhNMoN1JqxLiK+yBdSbQfFnDNY3udyDTZ2NeGsbUrMH"
    "/RmI4FF4yzng6hqwW/MftJNLabFxt32DZNb/3SUusVcDaLiCH6uUpkGv5Vwziq1yEXS57Q/T3mKmLiBGF0sWMJRss2BMHOLK1ZSV"
    "sKT99zV3WHehTH+4FBo7rG8ObosVh+dudTveIohC8tmQu2IYTolYPJLtJSkZCsgu4eH1RZ9c96KLHu2shSEByU+LI302SWXyYoGM"
    "ezFN/DJcg3iDqQUxm1p8udhtYLbHuZpmQ/Fut9jhqgx51TC8sEtptkow4Dhex+FQS1wt1jltS5QwrNoVJrWA1Yz/Si/KkfvRtTUk"
    "WhndLlgClhCmLr12SKe7LmU+tgeU82IN4r1dLlaL2oW30zDjCKi8XkyMqW4wBrpTEwg3O5V+RM1B+SCBdqnniLlQWAJuiYCKwLjM"
    "QihPARl5jrhQuyCcB0sQkBZI7xyURtuhNHWEtrqQ4E5r1rQ63QwNw78+e+0Losdzb589qck0Tx/+e+/sj33t3cKOPtF3rOz0tN3S"
    "rWvYwp1LNTHtDqqQdrwTc0wCMbmZs0RSd9kAu+c9W3anamsU+5Nyb+Z4TdRDv+qD1D9G3Pvb/w/Dkkb4"
)


@pytest.mark.parametrize("legacy_field", ["admissibility", "effective_independence"])
def test_current_input_rejects_legacy_caller_gate_predicates(legacy_field: str) -> None:
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        _promotion_input(**{legacy_field: True})


def test_fixed_time_n8_calibration_is_ledger_refused_and_stays_shadow() -> None:
    promotion_input = _promotion_input()
    session = _ledger_session(binding=promotion_input.design_problem_binding)
    receipt = run_canonical_promotion_sequence(
        promotion_input,
        confidence_ledger_session=session,
    )

    assert receipt.promoted is False
    assert receipt.status == "shadow"
    assert receipt.promotion_lane == "contract_testing"
    assert receipt.consumer_promotable is False
    assert receipt.non_promotable_reason == "non_production_anchor_scope"
    assert receipt.authority_derivation_trace is None
    assert receipt.risk_spend.total_declared_delta == 0.0
    assert receipt.risk_spend.within_budget is True
    calibration = _obligation(receipt, PromotionObligationClass.CALIBRATION)
    assert calibration.status == PromotionObligationStatus.FAILED
    assert "non_anytime_valid" in calibration.detail
    assert calibration.risk_spend is not None
    assert calibration.risk_spend.n11_confidence_ledger_ref
    check = next(
        item
        for item in session.receipt().checks
        if item.obligation_class == PromotionObligationClass.CALIBRATION
    )
    assert check.execution_status == "refused"
    assert check.refusal_code == "non_anytime_valid"
    assert check.spend_decimal == "0"
    assert receipt.confidence_ledger_receipt_id == session.receipt().receipt_id
    assert receipt.confidence_ledger_projection.ledger_receipt_id == session.receipt().receipt_id
    assert _obligation(receipt, PromotionObligationClass.EFFECT).status == (
        PromotionObligationStatus.SCOPE_INSUFFICIENT
    )
    assert _obligation(receipt, PromotionObligationClass.MEASUREMENT).status == (
        PromotionObligationStatus.SCOPE_INSUFFICIENT
    )
    assert validate_canonical_promotion_receipt(receipt) == ()


@pytest.mark.parametrize(
    ("status", "code"),
    [
        ("limited", "deployment_scope_limited"),
        ("not_established", "deployment_scope_not_established"),
    ],
)
def test_canonical_promotion_freezes_on_open_world_risk(
    status: str,
    code: str,
) -> None:
    gate = _open_world_gate(status=status, code=code)
    receipt = _run(_promotion_input(open_world_gate=gate))

    assert receipt.promoted is False
    assert f"open_world_risk:{code}" in receipt.refusal_reasons
    assert receipt.owner_projection.open_world_gate == gate


def test_canonical_promotion_freezes_on_scope_not_established() -> None:
    gate = _open_world_gate(
        status="not_established",
        code="deployment_scope_not_established",
    )
    receipt = _run(_promotion_input(open_world_gate=gate))

    assert receipt.status == "shadow"
    assert receipt.gate_outcome_hash == _gate_outcome_hash(
        receipt.obligations,
        open_world_gate=gate,
    )


def test_owner_projection_round_trips_exact_open_world_vector_identity() -> None:
    gate = _open_world_gate(
        status="not_established",
        code="deployment_scope_not_established",
    )

    receipt = _run(_promotion_input(open_world_gate=gate))
    restored = CanonicalPromotionReceipt.model_validate(receipt.model_dump(mode="json"))

    assert restored.owner_projection.open_world_gate == gate
    assert restored.gate_outcome_hash == receipt.gate_outcome_hash


def test_legacy_v3_history_is_exactly_readable_but_not_current_authority() -> None:
    frozen = json.loads(
        (REPO_ROOT / "architecture/policy_design_case/layer3_gy_promotion_contract.json").read_text(
            encoding="utf-8"
        )
    )
    payload = frozen["contract_lane_anytime_refusal"]
    owner = payload["owner_projection"]

    parsed = promotion_sequence_module.parse_canonical_promotion_history_receipt(payload)

    assert isinstance(parsed, promotion_sequence_module._LegacyCanonicalPromotionReceiptV3)
    assert owner["projection_hash"] == gy_content_hash(
        {key: value for key, value in owner.items() if key != "projection_hash"}
    )
    with pytest.raises(ValueError):
        CanonicalPromotionReceipt.model_validate(payload)
    assert validate_canonical_promotion_receipt(payload)[0]["code"] == (
        "legacy_open_world_gate_authority_not_admitted"
    )
    hybrid = deepcopy(payload)
    hybrid["owner_projection"]["open_world_gate"] = None
    with pytest.raises(ValueError):
        promotion_sequence_module.parse_canonical_promotion_history_receipt(hybrid)


def test_v4_v1_history_is_readable_but_cannot_be_current_authority() -> None:
    receipt = _run(_promotion_input())

    assert receipt.schema_version == "policyos.policy_design_case.layer3_gy.n9_promotion.v5"
    payload = _legacy_v4_history_payload(receipt)
    parsed = promotion_sequence_module.parse_canonical_promotion_history_receipt(payload)

    assert isinstance(parsed, promotion_sequence_module._LegacyCanonicalPromotionReceiptV4)
    assert parsed.model_dump(mode="json") == payload
    with pytest.raises(ValueError):
        CanonicalPromotionReceipt.model_validate(payload)
    assert validate_canonical_promotion_receipt(payload) == (
        {"code": "legacy_obligation_scope_v1_authority_not_admitted"},
    )


def test_round1_v5_v2_receipt_round_trips_but_cannot_regain_current_authority() -> None:
    raw = zlib.decompress(base64.b64decode(_ROUND1_V5_V2_RECEIPT_ZLIB_B64))

    assert len(raw) == 48_568
    assert hashlib.sha256(raw).hexdigest() == (
        "dba4a1ab7f374ea04044b171b0e163c6b0b1390089197fc64f96c2f0e86983c9"
    )
    payload = json.loads(raw)
    parsed = promotion_sequence_module.parse_canonical_promotion_history_receipt(payload)

    assert isinstance(parsed, CanonicalPromotionReceipt)
    assert parsed.schema_version.endswith(".v5")
    assert parsed.owner_projection.schema_version.endswith(".v3")
    assert {
        row.instance_scope_content_hash for row in parsed.obligations
    } == {
        promotion_sequence_module._obligation_instance_scope_content_hash(
            promotion_sequence_module._input_from_owner_projection(
                parsed.owner_projection,
                repo_root=REPO_ROOT,
            )
        )
    }
    assert parsed.model_dump_json().encode("utf-8") == raw
    assert validate_canonical_promotion_receipt(parsed)


def test_v1_scope_rows_cannot_be_restamped_as_current_authority() -> None:
    receipt = _run(_promotion_input())
    payload = _current_receipt_with_v1_scope_rows(receipt)
    restamped = CanonicalPromotionReceipt.model_validate(payload)

    assert {issue["code"] for issue in validate_canonical_promotion_receipt(restamped)} == {
        "obligation_instance_scope_mismatch"
    }


def test_current_owner_projection_requires_the_physical_open_world_key() -> None:
    receipt = _run(_promotion_input())
    payload = receipt.owner_projection.model_dump(mode="json")
    payload.pop("open_world_gate")

    with pytest.raises(ValueError):
        promotion_sequence_module.CanonicalPromotionOwnerProjection.model_validate(payload)

    assert receipt.schema_version == (
        promotion_sequence_module.CANONICAL_PROMOTION_SEQUENCE_SCHEMA_VERSION
    )
    assert receipt.owner_projection.schema_version == (
        promotion_sequence_module.CANONICAL_PROMOTION_OWNER_PROJECTION_SCHEMA_VERSION
    )
    assert "open_world_gate" in receipt.owner_projection.model_dump(mode="json")


def test_decision_front_rejects_unbound_open_world_receipt() -> None:
    gate = _open_world_gate(
        status="not_established",
        code="deployment_scope_not_established",
    )
    receipt = _run(_promotion_input(open_world_gate=gate))

    issues = validate_canonical_promotion_receipt(receipt)

    assert "open_world_resolver_not_established" in {str(issue["code"]) for issue in issues}


def test_decision_front_predicate_is_owned_by_canonical_promotion_sequence() -> None:
    promotion_input = _promotion_input()
    receipt = _run(promotion_input)
    promotion = PromotionPortObservation(
        status="not_promoted",
        reason="contract lane remains non-authoritative",
        receipts=(receipt.model_dump(mode="json"),),
    )

    canonical = promotion_sequence_module.promotion_receipt_allows_decision_front(
        promotion,
        promotion_input.candidate_summary,
        design_problem=None,
    )
    delegated = generation_cycle_module._promotion_receipt_allows_decision_front(
        promotion,
        promotion_input.candidate_summary,
        problem=None,
    )
    forged = promotion.model_copy(
        update={
            "receipts": (
                {
                    **receipt.model_dump(mode="json"),
                    "consumer_promotable": True,
                    "promotion_lane": "production",
                },
            )
        }
    )

    assert canonical is False and delegated is canonical
    assert (
        promotion_sequence_module.promotion_receipt_allows_decision_front(
            forged,
            promotion_input.candidate_summary,
            design_problem=None,
        )
        is False
    )


def test_n9_emits_additive_decisive_instances_with_deterministic_identity() -> None:
    promotion_input = _promotion_input()
    receipt = _run(promotion_input)

    class_gate_rows = [row for row in receipt.obligations if row.obligation_role == "class_gate"]
    decisive_rows = [
        row for row in receipt.obligations if row.obligation_role == "decisive_predicate"
    ]
    slot_rows = [
        row
        for row in receipt.obligations
        if row.obligation_class == PromotionObligationClass.SLOT
        and row.gate_id.value == "n8_transport"
    ]

    assert tuple(row.obligation_class for row in class_gate_rows) == tuple(PromotionObligationClass)
    assert [row.source_obligation_ref for row in decisive_rows] == [
        (
            "polisyos.runtime.quality.promotion_sequence."
            "run_canonical_promotion_sequence#effective_independence"
        ),
        (
            "polisyos.runtime.quality.generation_cycle.ValueGateReceipt#"
            "transport_wmr_hash_equals_receipt_wmr_hash"
        ),
        (
            "polisyos.runtime.quality.generation_cycle.ValueGateReceipt#"
            "outer_set_wmr_ref_equals_receipt_wmr_hash"
        ),
    ]
    assert len(slot_rows) == 3
    assert len(receipt.obligations) == 18
    assert len({row.obligation_instance_id for row in receipt.obligations}) == 18
    assert {row.identity_provenance for row in receipt.obligations} == {"recomputed"}

    expected_scope_hash = gy_content_hash(
        {
            "rule_version": "polisyos.policy_design_case.layer3_gy.n9_obligation_scope.v2",
            "promotion_rule_version": promotion_input.schema_version,
            "design_problem_id": promotion_input.design_problem_binding.design_problem_id,
            "problem_content_hash": (promotion_input.design_problem_binding.problem_content_hash),
            "candidate_id": promotion_input.candidate_summary.candidate_id,
            "candidate_content_hash": promotion_input.candidate_summary.content_hash,
            "operation_invocation_id": promotion_input.operation_invocation_id,
        }
    )
    assert {row.instance_scope_content_hash for row in receipt.obligations} == {expected_scope_hash}


def test_decisive_obligation_omission_keeps_class_totality_and_turns_authority_red() -> None:
    receipt = _run(_promotion_input())
    target = next(
        row
        for row in receipt.obligations
        if row.obligation_role == "decisive_predicate"
        and row.source_obligation_ref.endswith("#transport_wmr_hash_equals_receipt_wmr_hash")
    )
    obligations = tuple(
        row
        for row in receipt.obligations
        if row.obligation_instance_id != target.obligation_instance_id
    )
    class_gate_rows = tuple(row for row in obligations if row.obligation_role == "class_gate")
    edited = receipt.model_copy(
        update={
            "obligations": obligations,
            "gate_outcome_hash": _gate_outcome_hash(obligations),
        }
    )

    assert tuple(row.obligation_class for row in class_gate_rows) == tuple(PromotionObligationClass)
    assert validate_canonical_promotion_receipt(edited) == (
        {
            "code": "decisive_obligation_omitted",
            "obligation_instance_id": target.obligation_instance_id,
        },
    )


def test_n9_obligation_identity_replay_rejects_tamper_duplicate_and_substitution() -> None:
    promotion_input = _promotion_input()
    receipt = _run(promotion_input)
    replay = _run(promotion_input)
    assert [row.obligation_instance_id for row in replay.obligations] == [
        row.obligation_instance_id for row in receipt.obligations
    ]
    target = next(row for row in receipt.obligations if row.obligation_role == "decisive_predicate")

    tampered = target.model_copy(update={"source_obligation_content_hash": _hash("f")})
    tampered_rows = tuple(
        tampered if row.obligation_instance_id == target.obligation_instance_id else row
        for row in receipt.obligations
    )
    tampered_receipt = receipt.model_copy(
        update={
            "obligations": tampered_rows,
            "gate_outcome_hash": _gate_outcome_hash(tampered_rows),
        }
    )
    assert {issue["code"] for issue in validate_canonical_promotion_receipt(tampered_receipt)} == {
        "obligation_instance_identity_mismatch",
        "decisive_obligation_substituted",
    }

    duplicate_rows = (*receipt.obligations, target)
    duplicate_receipt = receipt.model_copy(
        update={
            "obligations": duplicate_rows,
            "gate_outcome_hash": _gate_outcome_hash(duplicate_rows),
        }
    )
    assert validate_canonical_promotion_receipt(duplicate_receipt) == (
        {
            "code": "duplicate_obligation_instance_id",
            "obligation_instance_id": target.obligation_instance_id,
        },
    )

    forged_source_ref = f"{target.source_obligation_ref}.forged"
    forged_id = gy_content_hash(
        {
            "rule_version": (
                "polisyos.policy_design_case.layer3_gy.n9_obligation_instance_identity.v1"
            ),
            "obligation_role": target.obligation_role,
            "obligation_class": target.obligation_class.value,
            "gate_id": target.gate_id.value,
            "source_obligation_ref": forged_source_ref,
            "source_obligation_content_hash": target.source_obligation_content_hash,
            "instance_scope_content_hash": target.instance_scope_content_hash,
        }
    )
    forged = target.model_copy(
        update={
            "source_obligation_ref": forged_source_ref,
            "obligation_instance_id": forged_id,
        }
    )
    forged_rows = tuple(
        forged if row.obligation_instance_id == target.obligation_instance_id else row
        for row in receipt.obligations
    )
    forged_receipt = receipt.model_copy(
        update={
            "obligations": forged_rows,
            "gate_outcome_hash": _gate_outcome_hash(forged_rows),
        }
    )
    assert {issue["code"] for issue in validate_canonical_promotion_receipt(forged_receipt)} == {
        "decisive_obligation_omitted",
        "unexpected_decisive_obligation_instance",
    }


def test_non_calibration_probabilistic_offer_is_ledger_accounted_and_refused() -> None:
    promotion_input = _promotion_input()
    session = _ledger_session(binding=promotion_input.design_problem_binding)

    receipt = run_canonical_promotion_sequence(
        promotion_input,
        confidence_ledger_session=session,
    )

    data = _obligation(receipt, PromotionObligationClass.DATA)
    assert data.status == PromotionObligationStatus.FAILED
    assert data.risk_spend is not None
    assert data.risk_spend.instrument == "owner_verified_e_process"
    check = next(
        item
        for item in session.receipt().checks
        if item.obligation_class == PromotionObligationClass.DATA
    )
    assert check.outcome == "preflight_refusal"
    assert check.refusal_code == "owner_theorem_unavailable"
    assert check.spend.fraction == 0
    assert validate_canonical_promotion_receipt(receipt) == ()


def test_registered_non_calibration_route_cannot_be_omitted_from_ledger() -> None:
    promotion_input = _promotion_input()
    session = _ledger_session(binding=promotion_input.design_problem_binding)

    receipt = run_canonical_promotion_sequence(
        promotion_input,
        confidence_ledger_session=session,
    )

    data = _obligation(receipt, PromotionObligationClass.DATA)
    assert data.status == PromotionObligationStatus.FAILED
    assert data.risk_spend is not None
    assert data.risk_spend.instrument == "owner_verified_e_process"
    checks = [
        item
        for item in session.receipt().checks
        if item.obligation_class == PromotionObligationClass.DATA
    ]
    assert len(checks) == 1
    assert checks[0].certificate_class == "n8_data_trust_promotion_candidate"
    assert checks[0].refusal_code == "owner_theorem_unavailable"
    assert validate_canonical_promotion_receipt(receipt) == ()


def test_caller_offer_is_only_an_equality_assertion_over_owner_recomputation() -> None:
    promotion_input = _promotion_input()
    registry = promotion_sequence_module.load_confidence_ledger_registry(
        REPO_ROOT / promotion_sequence_module.DEFAULT_REGISTRY_RELATIVE_PATH
    )
    expected = promotion_sequence_module._promotion_certificate_offers(
        promotion_input,
        registry=registry,
    )
    asserted = promotion_input.model_copy(update={"certificate_offers": (expected[-1],)})

    recomputed = promotion_sequence_module._promotion_certificate_offers(
        asserted,
        registry=registry,
    )

    assert recomputed == expected


def test_caller_offer_cannot_substitute_for_owner_recomputation() -> None:
    promotion_input = _promotion_input()
    registry = promotion_sequence_module.load_confidence_ledger_registry(
        REPO_ROOT / promotion_sequence_module.DEFAULT_REGISTRY_RELATIVE_PATH
    )
    expected = promotion_sequence_module._promotion_certificate_offers(
        promotion_input,
        registry=registry,
    )
    forged = expected[-1].model_copy(update={"owner_projection_hash": "sha256:" + "9" * 64})
    asserted = promotion_input.model_copy(update={"certificate_offers": (forged,)})

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        promotion_sequence_module._promotion_certificate_offers(
            asserted,
            registry=registry,
        )

    assert exc_info.value.code == "promotion_certificate_offer_assertion_mismatch"


def test_two_registered_instruments_over_one_owner_get_distinct_ledger_rows() -> None:
    promotion_input = _promotion_input()
    registry = promotion_sequence_module.load_confidence_ledger_registry(
        REPO_ROOT / promotion_sequence_module.DEFAULT_REGISTRY_RELATIVE_PATH
    )
    payload = registry.source_payload()
    payload["certificate_class_routes"].append(
        {
            "certificate_class": "n8_data_trust_sequential_test_candidate",
            "instrument_id": "owner_verified_sequential_test",
            "obligation_class": "data",
            "certificate_role": "promotion",
            "claim_polarity": "false_accept",
            "owner_ref": "polisyos.core.contracts.value_outer_set.DataTrust",
            "verifier_kernel_id": "n8_data_trust_recompute_v1",
            "verifier_ref": "polisyos.runtime.quality.promotion_sequence._data_obligation",
        }
    )
    session = _verification_ledger_session(
        binding=promotion_input.design_problem_binding,
        registry_source=payload,
    )

    offers = promotion_sequence_module._promotion_certificate_offers(
        promotion_input,
        registry=session.registry,
    )
    data_offers = [item for item in offers if item.claim.data_window_ref == "data-trust://unit"]
    assert len(data_offers) == 2
    assert len({item.certificate_ref for item in data_offers}) == 1
    assert len({item.owner_projection_hash for item in data_offers}) == 1
    assert len({item.request_key for item in data_offers}) == 2

    promotion_sequence_module._run_promotion_sequence_with_bound_session(
        promotion_input,
        confidence_ledger_session=session,
    )

    validated_ledger = validate_confidence_ledger_receipt(
        session.receipt(),
        session=session,
    )
    data_checks = [
        item
        for item in validated_ledger.checks
        if item.obligation_class == PromotionObligationClass.DATA
    ]
    assert len(data_checks) == 2
    assert len({item.instrument_id for item in data_checks}) == 2
    assert len({item.request_key for item in data_checks}) == 2


def test_registered_promotion_route_without_owner_producer_fails_before_spend() -> None:
    promotion_input = _promotion_input()
    registry = promotion_sequence_module.load_confidence_ledger_registry(
        REPO_ROOT / promotion_sequence_module.DEFAULT_REGISTRY_RELATIVE_PATH
    )
    payload = registry.source_payload()
    payload["certificate_class_routes"].append(
        {
            "certificate_class": "future_promotion_route_without_n9_owner_producer",
            "instrument_id": "owner_verified_e_process",
            "obligation_class": "data",
            "certificate_role": "promotion",
            "claim_polarity": "false_accept",
            "owner_ref": (
                "tools.quality.validation.layer3_gy_n13a_acquisition_census."
                "extract_route_projection"
            ),
            "verifier_kernel_id": "n10_route_projection_recompute_v1",
            "verifier_ref": (
                "tools.quality.validation."
                "check_layer3_gy_depth_n_universality_contract.validate_payload"
            ),
        }
    )
    session = _verification_ledger_session(
        binding=promotion_input.design_problem_binding,
        registry_source=payload,
    )

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        promotion_sequence_module._run_promotion_sequence_with_bound_session(
            promotion_input,
            confidence_ledger_session=session,
        )

    assert exc_info.value.code == "promotion_certificate_offer_owner_recomputation_unavailable"
    assert session.receipt().events == ()
    assert session.receipt().checks == ()
    assert session.receipt().total_spend.fraction == 0


def test_removing_code_owned_data_trust_route_fails_before_spend() -> None:
    promotion_input = _promotion_input()
    registry = promotion_sequence_module.load_confidence_ledger_registry(
        REPO_ROOT / promotion_sequence_module.DEFAULT_REGISTRY_RELATIVE_PATH
    )
    payload = registry.source_payload()
    payload["certificate_class_routes"] = [
        item
        for item in payload["certificate_class_routes"]
        if item["certificate_class"] != "n8_data_trust_promotion_candidate"
    ]
    session = _verification_ledger_session(
        binding=promotion_input.design_problem_binding,
        registry_source=payload,
    )

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        promotion_sequence_module._run_promotion_sequence_with_bound_session(
            promotion_input,
            confidence_ledger_session=session,
        )

    assert exc_info.value.code == "promotion_certificate_route_missing_for_owner_producer"
    assert exc_info.value.detail == "n8_data_trust_recompute_v1"
    assert session.receipt().events == ()
    assert session.receipt().checks == ()
    assert session.receipt().total_spend.fraction == 0


@pytest.mark.parametrize(
    ("field", "forged_value"),
    [
        ("owner_ref", "attacker.FakeOwner"),
        ("verifier_ref", "attacker.FakeVerifier"),
        ("obligation_class", "value"),
    ],
)
def test_relabelled_code_owned_owner_and_verifier_fail_before_spend(
    field: str,
    forged_value: str,
) -> None:
    promotion_input = _promotion_input()
    registry = promotion_sequence_module.load_confidence_ledger_registry(
        REPO_ROOT / promotion_sequence_module.DEFAULT_REGISTRY_RELATIVE_PATH
    )
    payload = registry.source_payload()
    data_route = next(
        item
        for item in payload["certificate_class_routes"]
        if item["certificate_class"] == "n8_data_trust_promotion_candidate"
    )
    data_route["instrument_id"] = "deterministic_owner_proof"
    data_route[field] = forged_value
    forged_owner_ref = str(data_route["owner_ref"])
    forged_verifier_ref = str(data_route["verifier_ref"])
    calls = {"resolver": 0, "verifier": 0}
    owner_projection = promotion_sequence_module._data_trust_owner_projection(promotion_input)

    def resolve(check: ConfidenceLedgerCheck) -> OwnerCertificateEvidence:
        calls["resolver"] += 1
        return OwnerCertificateEvidence(
            certificate_ref=check.certificate_ref,
            instrument_id=check.instrument_id,
            obligation_class=check.obligation_class,
            certificate_role=check.certificate_role,
            claim_polarity=check.claim_polarity,
            owner_ref=forged_owner_ref,
            owner_projection=owner_projection,
            certificate_class=check.certificate_class,
            claim_execution_binding_hash=check.claim_execution_binding_hash,
        )

    def verify(evidence: OwnerCertificateEvidence) -> OwnerCertificateVerification:
        calls["verifier"] += 1
        return OwnerCertificateVerification(
            verifier_ref=forged_verifier_ref,
            verifier_projection={
                "owner_projection_hash": recompute_confidence_owner_projection_hash(
                    evidence.owner_projection
                ),
                "claim_execution_binding_hash": evidence.claim_execution_binding_hash,
            },
            certificate_evidence_hash=recompute_confidence_owner_evidence_hash(evidence),
            claim_execution_binding_hash=evidence.claim_execution_binding_hash,
            supports_obligation=True,
        )

    session = _verification_ledger_session(
        binding=promotion_input.design_problem_binding,
        registry_source=payload,
        resolver=resolve,
        verifier=verify,
    )

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        promotion_sequence_module._run_promotion_sequence_with_bound_session(
            promotion_input,
            confidence_ledger_session=session,
        )

    assert exc_info.value.code == "promotion_certificate_route_owner_contract_mismatch"
    assert calls == {"resolver": 0, "verifier": 0}
    assert session.receipt().events == ()
    assert session.receipt().checks == ()
    assert session.receipt().total_spend.fraction == 0


def test_same_class_unrelated_claim_cannot_satisfy_compiled_obligation() -> None:
    promotion_input = _promotion_input()
    session = _ledger_session(binding=promotion_input.design_problem_binding)
    receipt = run_canonical_promotion_sequence(
        promotion_input,
        confidence_ledger_session=session,
    )
    data_check = next(
        item
        for item in session.receipt().checks
        if item.obligation_class == PromotionObligationClass.DATA
    )
    unrelated = data_check.model_copy(
        update={
            "certificate_ref": "future-owner://unrelated/certificate",
            "execution_status": "executed",
            "outcome": "supported",
            "anytime_valid": True,
            "supports_obligation": True,
            "eligible_for_promotion": True,
        }
    )
    compiled = promotion_sequence_module._data_obligation(promotion_input.value_receipt)

    bound = promotion_sequence_module._bind_certificate_checks_to_obligations(
        promotion_input,
        session.registry,
        (compiled,),
        (unrelated,),
        risk_spend=receipt.risk_spend,
    )

    assert bound[0].status == PromotionObligationStatus.FAILED
    assert "does not bind" in bound[0].detail


def test_multiple_eligible_offers_execute_before_next_offer_is_prepared() -> None:
    registry = promotion_sequence_module.load_confidence_ledger_registry(
        REPO_ROOT / promotion_sequence_module.DEFAULT_REGISTRY_RELATIVE_PATH
    )
    payload = registry.source_payload()
    instrument = next(
        item
        for item in payload["instruments"]
        if item["instrument_id"] == "constant_unit_e_process"
    )
    instrument["certificate_roles"] = ["promotion_conformance", "promotion"]
    payload["certificate_class_routes"].extend(
        {
            "certificate_class": f"test_eligible_route_{index}",
            "instrument_id": "constant_unit_e_process",
            "obligation_class": obligation_class.value,
            "certificate_role": "promotion",
            "claim_polarity": "false_accept",
            "owner_ref": f"test-owner://{index}",
            "verifier_kernel_id": "n8_data_trust_recompute_v1",
            "verifier_ref": "test-verifier://closed-constant-e-process",
        }
        for index, obligation_class in enumerate(
            (PromotionObligationClass.DATA, PromotionObligationClass.VALUE),
            start=1,
        )
    )
    session = _verification_ledger_session(registry_source=payload)
    offers = tuple(
        PromotionCertificateOffer(
            request_key=f"test://eligible-offer/{index}",
            certificate_class=f"test_eligible_route_{index}",
            certificate_ref=f"test-certificate://{index}",
            owner_projection_hash="sha256:" + str(index) * 64,
            claim=PredictableClaimSpec(
                claim_ref=f"test-claim://{index}",
                null_ref=f"test-null://{index}",
                claim_scope_ref=f"test-scope://{index}",
                data_window_ref="test-window://frozen",
                certificate_role="promotion",
                claim_polarity="false_accept",
            ),
        )
        for index in (1, 2)
    )

    checks = promotion_sequence_module._execute_promotion_certificate_offers(session, offers)

    assert tuple(item.execution_ordinal for item in checks) == (0, 1)
    assert all(item.outcome == "not_supported" for item in checks)


def test_supported_owner_bound_offer_round_trips_through_generic_validator() -> None:
    promotion_input = _promotion_input()
    assert promotion_input.value_receipt is not None
    unicode_trust = promotion_input.value_receipt.value_outer_set.data_trust.model_copy(
        update={"authority_ref": "data-trust://unit/дані"}
    )
    promotion_input = promotion_input.model_copy(
        update={
            "value_receipt": promotion_input.value_receipt.model_copy(
                update={
                    "value_outer_set": (
                        promotion_input.value_receipt.value_outer_set.model_copy(
                            update={"data_trust": unicode_trust}
                        )
                    )
                }
            )
        }
    )
    registry = promotion_sequence_module.load_confidence_ledger_registry(
        REPO_ROOT / promotion_sequence_module.DEFAULT_REGISTRY_RELATIVE_PATH
    )
    payload = registry.source_payload()
    data_route = next(
        item
        for item in payload["certificate_class_routes"]
        if item["certificate_class"] == "n8_data_trust_promotion_candidate"
    )
    data_route["instrument_id"] = "deterministic_owner_proof"
    data_owner_projection = promotion_sequence_module._data_trust_owner_projection(promotion_input)
    assert isinstance(data_owner_projection, dict)

    def resolve(check: ConfidenceLedgerCheck) -> OwnerCertificateEvidence:
        return OwnerCertificateEvidence(
            certificate_ref=check.certificate_ref,
            instrument_id=check.instrument_id,
            obligation_class=check.obligation_class,
            certificate_role=check.certificate_role,
            claim_polarity=check.claim_polarity,
            owner_ref="polisyos.core.contracts.value_outer_set.DataTrust",
            owner_projection=data_owner_projection,
            certificate_class=check.certificate_class,
            claim_execution_binding_hash=check.claim_execution_binding_hash,
        )

    def verify(evidence: OwnerCertificateEvidence) -> OwnerCertificateVerification:
        return OwnerCertificateVerification(
            verifier_ref="polisyos.runtime.quality.promotion_sequence._data_obligation",
            verifier_projection={
                "owner_projection_hash": recompute_confidence_owner_projection_hash(
                    evidence.owner_projection
                ),
                "claim_execution_binding_hash": evidence.claim_execution_binding_hash,
            },
            certificate_evidence_hash=recompute_confidence_owner_evidence_hash(evidence),
            claim_execution_binding_hash=evidence.claim_execution_binding_hash,
            supports_obligation=True,
        )

    session = _verification_ledger_session(
        binding=promotion_input.design_problem_binding,
        registry_source=payload,
        resolver=resolve,
        verifier=verify,
    )
    receipt = promotion_sequence_module._run_promotion_sequence_with_bound_session(
        promotion_input,
        confidence_ledger_session=session,
    )

    data = _obligation(receipt, PromotionObligationClass.DATA)
    data_check = next(
        item
        for item in session.receipt().checks
        if item.obligation_class == PromotionObligationClass.DATA
    )
    assert data.status == PromotionObligationStatus.SATISFIED, data.model_dump(mode="json")
    assert data_check.owner_binding is not None
    assert data_check.owner_binding.owner_projection_hash == (
        recompute_confidence_owner_projection_hash(data_owner_projection)
    )
    assert data.risk_spend is not None
    assert data.risk_spend.deterministic_proof is True
    assert receipt.owner_projection.epoch_validity_projection is None
    assert (
        promotion_sequence_module._validate_promotion_receipt_with_bound_session(
            receipt,
            repo_root=REPO_ROOT,
            candidate_summary=None,
            design_problem=None,
            value_receipt=None,
            open_world_resolver=None,
            epoch_validity_resolver=None,
            confidence_ledger_session=session,
            expected_authority_provenance="verification",
        )
        == ()
    )


def test_owner_content_change_rebinds_offer_even_when_owner_ref_is_stable() -> None:
    original = _promotion_input()
    assert original.value_receipt is not None
    original_trust = original.value_receipt.value_outer_set.data_trust
    changed_trust = original_trust.model_copy(
        update={"trust_cap": 0.8, "trust_multiplier": 0.8, "promotion_floor": 0.7}
    )
    changed_outer = original.value_receipt.value_outer_set.model_copy(
        update={"data_trust": changed_trust}
    )
    changed_receipt = original.value_receipt.model_copy(update={"value_outer_set": changed_outer})
    changed = original.model_copy(update={"value_receipt": changed_receipt})
    registry = promotion_sequence_module.load_confidence_ledger_registry(
        REPO_ROOT / promotion_sequence_module.DEFAULT_REGISTRY_RELATIVE_PATH
    )

    original_offer = next(
        item
        for item in promotion_sequence_module._promotion_certificate_offers(
            original,
            registry=registry,
        )
        if item.certificate_class == "n8_data_trust_promotion_candidate"
    )
    changed_offer = next(
        item
        for item in promotion_sequence_module._promotion_certificate_offers(
            changed,
            registry=registry,
        )
        if item.certificate_class == "n8_data_trust_promotion_candidate"
    )

    assert original_offer.certificate_ref == changed_offer.certificate_ref
    assert original_offer.owner_projection_hash != changed_offer.owner_projection_hash
    assert original_offer.claim.claim_scope_ref != changed_offer.claim.claim_scope_ref
    session = _ledger_session(binding=original.design_problem_binding)
    run_canonical_promotion_sequence(original, confidence_ledger_session=session)

    run_canonical_promotion_sequence(changed, confidence_ledger_session=session)

    data_checks = [
        item
        for item in session.receipt().checks
        if item.obligation_class == PromotionObligationClass.DATA
    ]
    assert len(data_checks) == 2
    assert len({item.request_key for item in data_checks}) == 2
    assert len({item.request_fingerprint for item in data_checks}) == 2


def test_candidate_content_change_rebinds_offer_even_when_candidate_id_is_stable() -> None:
    original = _promotion_input()
    changed_summary = original.candidate_summary.model_copy(update={"content_hash": _hash("7")})
    changed = original.model_copy(update={"candidate_summary": changed_summary})
    registry = promotion_sequence_module.load_confidence_ledger_registry(
        REPO_ROOT / promotion_sequence_module.DEFAULT_REGISTRY_RELATIVE_PATH
    )

    original_offers = promotion_sequence_module._promotion_certificate_offers(
        original,
        registry=registry,
    )
    changed_offers = promotion_sequence_module._promotion_certificate_offers(
        changed,
        registry=registry,
    )
    assert all(
        original_offer.claim.claim_scope_ref != changed_offer.claim.claim_scope_ref
        for original_offer, changed_offer in zip(original_offers, changed_offers, strict=True)
    )
    session = _ledger_session(binding=original.design_problem_binding)
    run_canonical_promotion_sequence(original, confidence_ledger_session=session)

    run_canonical_promotion_sequence(changed, confidence_ledger_session=session)

    checks = session.receipt().checks
    assert len(checks) == 4
    assert len({item.request_key for item in checks}) == 4
    assert len({item.request_fingerprint for item in checks}) == 4


def test_unknown_non_calibration_offer_fail_closes_before_spend() -> None:
    offer = _probabilistic_offer(PromotionObligationClass.DATA).model_copy(
        update={"certificate_class": "unregistered_future_certificate_class"}
    )
    promotion_input = _promotion_input(certificate_offers=(offer,))
    session = _ledger_session(binding=promotion_input.design_problem_binding)

    with pytest.raises(ConfidenceLedgerError, match="certificate_class_route_missing"):
        run_canonical_promotion_sequence(
            promotion_input,
            confidence_ledger_session=session,
        )

    assert session.receipt().total_spend.fraction == 0
    assert session.receipt().checks == ()


def test_n9_receipt_authorizes_only_narrow_projection_and_current_head() -> None:
    receipt = _run(_promotion_input())
    payload = receipt.model_dump(mode="json")

    assert "confidence_ledger_receipt" not in payload
    assert receipt.confidence_ledger_scope_ref == (receipt.confidence_ledger_projection.scope_id)
    assert receipt.confidence_ledger_head_id == (receipt.confidence_ledger_projection.head_event_id)
    assert receipt.confidence_ledger_head_ref == (
        receipt.confidence_ledger_projection.head_event_ref
    )


def test_n9_owner_replay_projection_round_trips_through_json() -> None:
    receipt = _run(_promotion_input())

    restored = CanonicalPromotionReceipt.model_validate(receipt.model_dump(mode="json"))

    assert restored == receipt
    assert validate_canonical_promotion_receipt(restored) == ()


def test_ungrounded_candidate_stays_shadow_by_real_grounding_owner() -> None:
    receipt = _run(
        _promotion_input(
            summary=_summary(current_valid=False, grounding_status="grounded_shadow"),
        )
    )

    assert receipt.promoted is False
    assert "identification:single_obligation_fail" in receipt.refusal_reasons


def test_uncalibrated_candidate_stays_shadow() -> None:
    value = _value_receipt(calibration_status="blocked")
    receipt = _run(_promotion_input(value_receipt=value))

    assert receipt.promoted is False
    assert "calibration:single_obligation_fail" in receipt.refusal_reasons


def test_untransportable_candidate_stays_shadow() -> None:
    value = _value_receipt(transport_status="blocked")
    receipt = _run(_promotion_input(value_receipt=value))

    assert receipt.promoted is False
    assert "slot:single_obligation_fail" in receipt.refusal_reasons


def test_timeout_unknown_never_promotes_or_fabricates_block() -> None:
    receipt = _run(_promotion_input(force_proof_timeout=True))

    assert receipt.promoted is False
    assert receipt.status == "shadow"
    effect = _obligation(receipt, PromotionObligationClass.EFFECT)
    assert effect.status == PromotionObligationStatus.UNKNOWN
    assert "effect:proof_timeout" in receipt.refusal_reasons


def test_lower_boundary_wins_over_optimistic_declared_transform() -> None:
    receipt = _run(
        _promotion_input(
            declared_authority_transform={
                "requested_evidence_kind": "measurement",
                "requested_decision_grade": "decision_admissible",
            }
        )
    )

    assert receipt.promoted is False
    assert receipt.computed_authority_boundary.decision_grade == "advisory_admissible"
    assert receipt.authority_derivation_trace is None
    assert "calibration:single_obligation_fail" in receipt.refusal_reasons


def test_no_self_promotion_rejected_by_trace_guard() -> None:
    artifact = ArtifactRef(
        artifact_id="n9.self.promotion",
        artifact_type="runtime.quality.n9_promotion_receipt",
        content_hash=_hash("1"),
        schema_ref="policyos.policy_design_case.layer3_gy.n9_promotion.v2",
        uri="pdc://n9/self",
        version="v1",
    )

    with pytest.raises(ValueError, match="authority_transform hints cannot self-promote"):
        AuthorityDerivationTrace(
            operation_invocation_id="n9.self",
            output_artifact_ref=artifact,
            declared_authority_transform={
                "requested_evidence_kind": "measurement",
                "requested_decision_grade": "decision_admissible",
            },
            computed_evidence_kind="transport",
            computed_decision_grade="advisory_admissible",
            producer_root_classes=["llm_candidate"],
            method_classification="source_flip_probe",
            applicability_result_ref="n9://probe",
            resulting_authority_boundary_ref="n9.self.boundary",
            transform_mismatch_disposition="upgraded",
        )


def test_no_cg2_owner_grant_stays_shadow() -> None:
    receipt = _run(
        _promotion_input(
            grounding_decision_certificate=None,
            credal_reference=None,
        )
    )

    assert receipt.promoted is False
    assert "identification:single_obligation_fail" in receipt.refusal_reasons
    assert (
        "resolve_grounding_decision_promotability"
        in _obligation(
            receipt,
            PromotionObligationClass.IDENTIFICATION,
        ).owner_ref
    )


def test_cg2_open_admissibility_obligation_keeps_promotion_red() -> None:
    reference = _credal_reference()
    engine = GroundingRelationEngine(reference)
    cg1 = engine.certificate_for(
        _pure_synonym_probe(engine),
        proposal_id="n9-cg2-open-admissibility",
    )
    payload = cg1.model_dump(mode="json")
    payload["proposal_signature"]["hypotheses"][0]["signature"]["admissibility"] = (
        "candidate_unverified"
    )
    provisional = cg1.__class__.model_validate(payload)
    payload["content_hash"] = recompute_grounding_relation_content_hash(provisional)
    payload["certificate_id"] = f"cg1_cert_{payload['content_hash'].removeprefix('sha256:')[:16]}"
    open_cg1 = cg1.__class__.model_validate(payload)
    decision = GroundingBindGate.for_contract_testing(
        reference,
        calibration_seed_anchor=True,
        disable_certificate_revalidation=True,
    ).certificate_for(open_cg1)

    receipt = _run(
        _promotion_input(
            grounding_decision_certificate=decision,
            credal_reference=reference,
        )
    )

    assert decision.decision == "abstain"
    assert "admissibility_closed" in decision.open_obligations
    assert receipt.promoted is False
    identification = _obligation(receipt, PromotionObligationClass.IDENTIFICATION)
    assert identification.status == PromotionObligationStatus.FAILED
    assert "identification:single_obligation_fail" in receipt.refusal_reasons
    assert "not_bind_decision" in identification.detail


def test_contract_testing_bind_receipt_is_intrinsically_non_promotable() -> None:
    receipt = _run(_promotion_input())

    assert receipt.promoted is False
    assert receipt.promotion_lane == "contract_testing"
    assert receipt.consumer_promotable is False
    assert receipt.non_promotable_reason == "non_production_anchor_scope"


def test_scope_insufficient_obligation_does_not_vacuously_pass() -> None:
    receipt = _run(_promotion_input(g4_governed_promotion_ref=None))

    assert receipt.promoted is False
    assert receipt.consumer_promotable is False
    param = _obligation(receipt, PromotionObligationClass.PARAM)
    assert param.status == PromotionObligationStatus.SCOPE_INSUFFICIENT
    assert param.semantic_scope == "scope_insufficient"
    vacuous_value = param.model_copy(
        update={
            "status": PromotionObligationStatus.SATISFIED,
            "reason": None,
            "semantic_scope": "scope_insufficient",
        }
    )
    obligations = tuple(
        vacuous_value
        if item.obligation_role == "class_gate"
        and item.obligation_class == PromotionObligationClass.PARAM
        else item
        for item in receipt.obligations
    )
    gate_outcome_hash = _gate_outcome_hash(obligations)
    edited = receipt.model_copy(
        update={
            "obligations": obligations,
            "gate_outcome_hash": gate_outcome_hash,
        }
    )

    issues = validate_canonical_promotion_receipt(edited)

    assert {issue["code"] for issue in issues} == {"obligation_class_vacuously_passed"}


def test_scope_insufficient_cannot_mint_production_authority() -> None:
    receipt = _run(_promotion_input())
    edited = receipt.model_copy(
        update={
            "promoted": True,
            "promotion_lane": "production",
            "consumer_promotable": True,
        }
    )

    issues = validate_canonical_promotion_receipt(edited)

    assert "scope_insufficient_authority_laundering" in {issue["code"] for issue in issues}


def test_unseen_non_panel_value_receipt_flows_unchanged() -> None:
    value = _value_receipt(
        method_fqn="frontier.unseen.scenario_set@1", representation="scenario_set"
    )
    receipt = _run(_promotion_input(value_receipt=value))

    assert receipt.promoted is False
    assert receipt.value_method_family == "frontier.unseen.scenario_set@1"
    assert receipt.value_receipt_ref == value.value_ref


def test_forged_g4_ref_is_refused_by_owner_resolution() -> None:
    receipt = _run(_promotion_input(g4_governed_promotion_ref="pdc://fake/g4/not-resolved"))

    assert receipt.promoted is False
    param = _obligation(receipt, PromotionObligationClass.PARAM)
    assert param.status == PromotionObligationStatus.FAILED
    assert "governed_promotion_record_not_found" in param.detail


def test_gyk_witness_pointer_is_not_a_supported_input() -> None:
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        _promotion_input(entailment_witness_ref="gyk://forged-witness")


def test_invented_measurement_marker_does_not_supply_authority() -> None:
    value = _value_receipt()
    marked_value = value.value_outer_set.model_copy(
        update={"calibration_scope": {"measurement_status": "pass"}}
    )
    receipt = _run(
        _promotion_input(value_receipt=value.model_copy(update={"value_outer_set": marked_value}))
    )
    measurement = _obligation(receipt, PromotionObligationClass.MEASUREMENT)
    assert measurement.status == PromotionObligationStatus.SCOPE_INSUFFICIENT
    assert measurement.owner_ref.endswith("MeasurementRootProducer.produce_from_catalog")
    assert "bridge_missing" in measurement.detail


def _independence_portfolio_design() -> dict[str, object]:
    return {
        "schema_version": "policyos.runtime.policy_design_case.evidence_portfolio_design.v1",
        "portfolio_id": "portfolio-n9-dependent",
        "claim_ids": ["claim-n9"],
        "predeclared": True,
        "declared_at": "2026-08-30T08:00:00+00:00",
        "declared_before_producer_execution": True,
        "authority_level": "production",
        "strands": [
            {
                "strand_id": "literature-strand",
                "claim_id": "claim-n9",
                "authority_level": "production",
                "candidate_data_source_families": ["academic_evidence"],
                "candidate_method_families": ["quasi_experimental_panel"],
                "defensible_specification_space": {"primary_estimand": "ATT"},
                "inclusion_rules": ["Include independently produced studies."],
                "exclusion_rules": ["Exclude duplicate reports of one study."],
                "disconfirming_lines": [{"line_id": "counter-required", "required": True}],
                "synthesis_rules": {"strategy": "effective_independence"},
                "stopping_rules": {"minimum_effective_independent_evidence_count": 2},
                "cost_proportionality": {"budget_tier": "standard"},
            }
        ],
        "candidate_data_source_families": ["academic_evidence"],
        "candidate_method_families": ["quasi_experimental_panel"],
        "inclusion_rules": ["Prefer production evidence."],
        "exclusion_rules": ["Reject raw-count inflation."],
        "disconfirming_lines": ["counter-required"],
        "synthesis_rules": {"strategy": "effective_independence"},
        "stopping_rules": {"minimum_effective_independent_evidence_count": 2},
        "cost_proportionality": {"budget_tier": "standard"},
        "cas_ref": _hash("a"),
        "runtime_event_ref": _hash("b"),
    }


def _independence_line(line_id: str, *, primary_source: str) -> dict[str, Any]:
    return {
        "schema_version": "policyos.runtime.policy_design_case.evidence_line.v1",
        "line_id": line_id,
        "portfolio_id": "portfolio-n9-dependent",
        "portfolio_strand_id": "literature-strand",
        "claim_id": "claim-n9",
        "evidence_strand": "literature",
        "polarity": "support",
        "quality_score": 1.0,
        "source_refs": [f"source:{line_id}"],
        "primary_source": primary_source,
        "retrieval_path": f"scholar-search:{line_id}",
        "source_lineage": {
            "source_id": primary_source,
            "source_ref": f"source:{line_id}",
            "lineage_refs": [f"lineage:{line_id}"],
            "corpus_id": "dataset-n9",
            "corpus_ancestry": ["dataset-n9"],
            "snapshot_id": "snapshot-n9",
            "preprocessing": "prep-n9",
            "transformation_lineage": ["transform:dataset-n9:prep-n9"],
            "retrieval_path": f"scholar-search:{line_id}",
        },
        "underlying_study_id": "study-shared-n9",
        "legal_authority": ["research-use-permit-2026"],
        "author_ids": ["author:n9"],
        "institution_ids": ["institution:n9"],
        "sponsor_ids": ["sponsor:n9"],
        "dataset_id": "dataset-n9",
        "corpus_ancestry": ["dataset-n9"],
        "snapshot_id": "snapshot-n9",
        "subject_pool": "msme-credit-applicants",
        "preprocessing_pipeline_id": "prep-n9",
        "transformation_lineage": ["transform:dataset-n9:prep-n9"],
        "method_id": f"foundry.did.{line_id}",
        "method_family": "difference_in_differences",
        "method_assumptions": ["parallel-trends", "no-anticipation"],
        "identification_strategy_id": "did-identification",
        "shared_failure_modes": ["selection-on-unobservables"],
        "proof_reuse_status": "fresh_proof",
        "llm_generation_path": {
            "model": "none",
            "prompt_ref": "deterministic-producer",
            "retrieval_ref": f"scholar-search:{line_id}",
        },
        "simulation_dgp": {
            "dgp_ref": "not_simulated",
            "calibration_ref": "not_applicable",
            "assumption_family": "not_applicable",
        },
        "participation_sample_frame": "not_participation_evidence",
        "concept_spine_refs": ["concept-spine:msme-credit"],
        "jurisdiction": "UA",
        "time_roles": {
            "publication_time": "2025-01-01",
            "retrieval_time": "2026-08-30T09:00:00+00:00",
            "legal_valid_time": "2026-01-01/2026-12-31",
        },
        "specification_id": f"spec:{line_id}",
        "producer_identity": {
            "component": "polisyos.scholar.evidence",
            "version": "2026.08.30",
            "owner": "team-science-quality",
        },
        "execution_context": {
            "run_id": "run-n9",
            "job_id": f"job:{line_id}",
            "tenant_id": "tenant-prod",
            "trace_id": f"trace:{line_id}",
        },
        "evidence_ref": _hash("c"),
        "runtime_event_ref": _hash("d"),
    }


def test_real_dependent_independence_graph_refuses_legacy_true(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        _promotion_input(effective_independence=True)

    promotion_input = _promotion_input()
    repository = promotion_sequence_module.N9PromotionEvidenceBridgeRepository(
        store=FileSystemCAS(tmp_path / "cas")
    )
    bridge_ref = repository.persist_effective_independence(
        promotion_input=promotion_input,
        evidence_lines=(
            _independence_line("publication-1", primary_source="journal"),
            _independence_line("publication-2", primary_source="working-paper"),
        ),
        portfolio_designs=(_independence_portfolio_design(),),
        graph_id="effective-independence:n9-dependent",
    )
    bridged_input = promotion_input.model_copy(
        update={"producer_root_refs": (bridge_ref,)}
    )

    receipt = run_canonical_promotion_sequence(
        bridged_input,
        confidence_ledger_session=_ledger_session(binding=bridged_input.design_problem_binding),
        promotion_evidence_resolver=repository,
    )
    rows = tuple(
        row
        for row in receipt.obligations
        if row.source_obligation_ref.endswith("#effective_independence")
    )

    assert len(rows) == 1
    assert rows[0].status == PromotionObligationStatus.FAILED
    assert rows[0].owner_ref.endswith("build_effective_independence_graph")
    assert "dependent_evidence_collapsed" in rows[0].detail
    assert "data:single_obligation_fail" in promotion_sequence_module._refusal_reasons(
        receipt.obligations,
        risk_spend=receipt.risk_spend,
    )


def test_real_measurement_root_resolves_and_binds_into_n9(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    catalog = build_slice0_fixture_catalog_graph(tmp_path)
    manifest = load_workspace_fixture_manifest("ua_msme_credit_worldbank_measurement")
    envelope = MeasurementRootProducer(artifact_store=store).produce_from_catalog(
        manifest,
        catalog,
    )
    promotion_input = _promotion_input()
    repository = promotion_sequence_module.N9PromotionEvidenceBridgeRepository(store=store)
    bridge_ref = repository.persist_measurement_root(
        promotion_input=promotion_input,
        envelope=envelope,
    )
    bridged_input = promotion_input.model_copy(
        update={"producer_root_refs": (bridge_ref,)}
    )

    receipt = run_canonical_promotion_sequence(
        bridged_input,
        confidence_ledger_session=_ledger_session(binding=bridged_input.design_problem_binding),
        promotion_evidence_resolver=repository,
    )

    measurement = _obligation(receipt, PromotionObligationClass.MEASUREMENT)
    assert measurement.status == PromotionObligationStatus.SATISFIED
    assert measurement.owner_ref.endswith("MeasurementRootProducer.produce_from_catalog")
    assert envelope.payload_ref in measurement.evidence_refs

    unresolved = _run(bridged_input)
    unresolved_measurement = _obligation(unresolved, PromotionObligationClass.MEASUREMENT)
    assert unresolved_measurement.status == PromotionObligationStatus.SCOPE_INSUFFICIENT
    assert "evidence_not_established" in unresolved_measurement.detail


def test_eval_safety_names_the_missing_promotion_authority_without_reusing_o0() -> None:
    data_only = _run(_promotion_input())
    pilot_value = _value_receipt().model_copy(update={"evaluation_mode": "field_pilot"})
    pilot = _run(_promotion_input(value_receipt=pilot_value))

    data_only_gate = _obligation(data_only, PromotionObligationClass.EVAL_SAFETY)
    pilot_gate = _obligation(pilot, PromotionObligationClass.EVAL_SAFETY)
    assert data_only_gate.status == PromotionObligationStatus.NOT_APPLICABLE_DATA_ONLY
    assert data_only_gate.owner_ref.endswith("_eval_safety_obligation")
    assert pilot_gate.status == PromotionObligationStatus.SCOPE_INSUFFICIENT
    assert pilot_gate.owner_ref == "absent/unallocated"
    assert "producer_missing" in pilot_gate.detail
    assert "forbids promotion use" in pilot_gate.detail


def test_n5_coupling_blocker_refuses_coupling() -> None:
    receipt = _run(
        _promotion_input(
            summary=_summary().model_copy(
                update={"value_blockers": ("n5_coupling_blocked",)}
            )
        )
    )

    coupling = _obligation(receipt, PromotionObligationClass.COUPLING)
    assert coupling.status == PromotionObligationStatus.FAILED
    assert coupling.owner_ref.endswith("SimulationPortObservation.authority_blockers")
    assert "n5_coupling_blocked" in coupling.evidence_refs
    production_reasons = promotion_sequence_module._refusal_reasons(
        receipt.obligations,
        risk_spend=receipt.risk_spend,
    )
    assert "coupling:single_obligation_fail" in production_reasons


def test_supported_n5_coupling_path_satisfies_coupling() -> None:
    receipt = _run(_promotion_input())

    coupling = _obligation(receipt, PromotionObligationClass.COUPLING)

    assert coupling.status == PromotionObligationStatus.SATISFIED
    assert coupling.owner_ref.endswith("SimulationPortObservation.authority_blockers")


def test_effective_independence_missing_is_explicit_decisive_nonreceipt() -> None:
    receipt = _run(_promotion_input())

    rows = tuple(
        row
        for row in receipt.obligations
        if row.obligation_role == "decisive_predicate"
        and row.source_obligation_ref.endswith("#effective_independence")
    )

    assert len(rows) == 1
    assert rows[0].status == PromotionObligationStatus.SCOPE_INSUFFICIENT
    assert rows[0].owner_ref == "absent/unallocated"
    assert "producer_missing" in rows[0].detail
    production_reasons = promotion_sequence_module._refusal_reasons(
        receipt.obligations,
        risk_spend=receipt.risk_spend,
    )
    assert "data:scope_insufficient" in production_reasons


def test_data_trust_typed_fields_fail_data_obligation() -> None:
    value = _value_receipt()
    data_bad = value.value_outer_set.model_copy(
        update={
            "data_trust": DataTrust(
                tier="unit",
                trust_cap=0.2,
                trust_multiplier=1.0,
                promotion_floor=0.5,
                authority_ref="data-trust://unit/insufficient",
            )
        }
    )
    receipt = _run(
        _promotion_input(value_receipt=value.model_copy(update={"value_outer_set": data_bad}))
    )
    assert _obligation(receipt, PromotionObligationClass.DATA).status == (
        PromotionObligationStatus.FAILED
    )


def test_s6_typed_posture_fails_implementation_obligation() -> None:
    s6_bad = _s6_posture().model_copy(
        update={
            "overall_posture": "blocked",
            "limitation_summary": "S6 capacity feasibility owner blocked the candidate.",
        }
    )
    receipt = _run(_promotion_input(s6_blind_spot_posture=s6_bad))
    assert _obligation(receipt, PromotionObligationClass.IMPLEMENTATION).status == (
        PromotionObligationStatus.FAILED
    )


def test_reintroduced_champion_path_turns_strangle_receipt_red() -> None:
    receipt = LegacyPromotionStrangleReceipt.recompute()

    assert receipt.status == "strangled"
    assert receipt.live_policy_champion_callers == ()


def test_hand_edited_confidence_projection_is_rejected() -> None:
    receipt = _run(_promotion_input())
    projection = receipt.confidence_ledger_projection.model_copy(
        update={"projection_hash": _hash("9")}
    )
    edited = receipt.model_copy(update={"confidence_ledger_projection": projection})

    issues = validate_canonical_promotion_receipt(edited)

    assert {issue["code"] for issue in issues} == {"confidence_ledger_projection_drift"}


def test_caller_cannot_supply_authoritative_risk_spends() -> None:
    supplied = PromotionRiskSpendRecord(
        obligation_class=PromotionObligationClass.CALIBRATION,
        certificate_ref="caller://forged-risk-spend",
        instrument="caller_claimed_anytime_valid",
        certificate_role="promotion",
        claim_polarity="false_accept",
        declared_delta_spend=0.0,
        n11_confidence_ledger_ref="confidence-check:sha256:" + "1" * 64,
    )

    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        _promotion_input(risk_spends=(supplied,))


def test_standalone_promotion_requires_non_optional_authority_ledger_session() -> None:
    parameter = signature(run_canonical_promotion_sequence).parameters["confidence_ledger_session"]

    assert parameter.default is Parameter.empty
    assert (
        get_type_hints(run_canonical_promotion_sequence)["confidence_ledger_session"]
        is ConfidenceLedgerSession
    )


def test_n9_rejects_session_bound_to_a_different_design_problem() -> None:
    promotion_input = _promotion_input()
    unrelated_session = _ledger_session(
        binding=_problem_binding(run_ref="unrelated-design-problem")
    )

    with pytest.raises(ValueError, match="confidence_ledger_scope_binding_mismatch"):
        run_canonical_promotion_sequence(
            promotion_input,
            confidence_ledger_session=unrelated_session,
        )


def test_value_receipt_candidate_mismatch_fails_closed_before_accounting() -> None:
    value = _value_receipt().model_copy(update={"candidate_id": "candidate_from_another_owner"})

    with pytest.raises(ValueError, match="promotion_value_candidate_binding_mismatch"):
        _promotion_input(value_receipt=value)


def test_verification_ledger_session_cannot_run_n9_authority_path() -> None:
    with pytest.raises(ValueError, match="confidence_ledger_authority_session_required"):
        run_canonical_promotion_sequence(
            _promotion_input(),
            confidence_ledger_session=_verification_ledger_session(),
        )


def test_private_verification_sequence_stamps_receipt_non_consumer_promotable() -> None:
    promotion_input = _promotion_input()
    session = _verification_ledger_session(binding=promotion_input.design_problem_binding)

    receipt = promotion_sequence_module._run_canonical_promotion_sequence_for_verification(
        promotion_input,
        confidence_ledger_session=session,
    )

    assert receipt.confidence_ledger_projection.authority_provenance == "verification"
    assert receipt.consumer_promotable is False
    assert receipt.non_promotable_reason == "verification_only_replay"


def test_private_verification_boundary_rejects_alternate_registry() -> None:
    promotion_input = _promotion_input()
    canonical_session = _verification_ledger_session(binding=promotion_input.design_problem_binding)
    receipt = promotion_sequence_module._run_canonical_promotion_sequence_for_verification(
        promotion_input,
        confidence_ledger_session=canonical_session,
    )
    alternate_payload = deepcopy(canonical_session.registry.source_payload())
    alternate_payload["schedule_profiles"][0]["mass"]["denominator"] = 2
    alternate_session = _verification_ledger_session(
        binding=promotion_input.design_problem_binding,
        registry_source=alternate_payload,
    )

    with pytest.raises(
        ValueError,
        match="confidence_ledger_verification_registry_invalid",
    ):
        promotion_sequence_module._run_canonical_promotion_sequence_for_verification(
            promotion_input,
            confidence_ledger_session=alternate_session,
        )
    with pytest.raises(
        ValueError,
        match="confidence_ledger_verification_registry_invalid",
    ):
        CanonicalN9PromotionPort._for_verification(
            repo_root=REPO_ROOT,
            confidence_ledger_session=alternate_session,
        )

    assert promotion_sequence_module._validate_canonical_promotion_receipt_for_verification(
        receipt,
        repo_root=REPO_ROOT,
        confidence_ledger_session=alternate_session,
    ) == ({"code": "confidence_ledger_verification_registry_invalid"},)


def test_public_validator_exposes_no_ledger_session_injection() -> None:
    assert (
        "confidence_ledger_session"
        not in signature(validate_canonical_promotion_receipt).parameters
    )


def test_public_validator_rejects_verification_before_opening_authority_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    promotion_input = _promotion_input()
    session = _verification_ledger_session(binding=promotion_input.design_problem_binding)
    receipt = promotion_sequence_module._run_canonical_promotion_sequence_for_verification(
        promotion_input,
        confidence_ledger_session=session,
    )

    def _forbid_authority_open(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("verification receipt touched canonical ledger namespace")

    monkeypatch.setattr(
        promotion_sequence_module,
        "_open_projected_confidence_ledger_session",
        _forbid_authority_open,
    )

    issues = validate_canonical_promotion_receipt(receipt)

    assert issues == ({"code": "confidence_ledger_authority_provenance_invalid"},)


def test_private_verification_revalidator_recomputes_current_head() -> None:
    promotion_input = _promotion_input()
    session = _verification_ledger_session(binding=promotion_input.design_problem_binding)
    receipt = promotion_sequence_module._run_canonical_promotion_sequence_for_verification(
        promotion_input,
        confidence_ledger_session=session,
    )

    issues = promotion_sequence_module._validate_canonical_promotion_receipt_for_verification(
        receipt,
        repo_root=REPO_ROOT,
        candidate_summary=promotion_input.candidate_summary,
        value_receipt=promotion_input.value_receipt,
        confidence_ledger_session=session,
    )

    assert issues == ()


def test_private_verification_revalidator_requires_loaded_owner_repo(
    tmp_path: Path,
) -> None:
    promotion_input = _promotion_input()
    session = _verification_ledger_session(binding=promotion_input.design_problem_binding)
    receipt = promotion_sequence_module._run_canonical_promotion_sequence_for_verification(
        promotion_input,
        confidence_ledger_session=session,
    )

    issues = promotion_sequence_module._validate_canonical_promotion_receipt_for_verification(
        receipt,
        repo_root=tmp_path,
        confidence_ledger_session=session,
    )

    assert issues == ({"code": "verification_owner_repo_root_invalid"},)


def test_verification_projection_is_not_n9_authority_provenance() -> None:
    receipt = _run(_promotion_input())
    projection = receipt.confidence_ledger_projection.model_copy(
        update={"authority_provenance": "verification"}
    )
    edited = receipt.model_copy(update={"confidence_ledger_projection": projection})

    issues = validate_canonical_promotion_receipt(edited)

    assert "confidence_ledger_authority_provenance_invalid" in {issue["code"] for issue in issues}


def test_schedule_slot_is_reserved_before_obligation_outcomes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, object]] = []
    promotion_input = _promotion_input()
    session = _ledger_session(
        run_ref="ledger-run:n9-ordering",
        binding=promotion_input.design_problem_binding,
    )
    original_prepare_check = ConfidenceLedgerSession.prepare_check

    def _record_prepare_check(
        current: ConfidenceLedgerSession,
        **kwargs: object,
    ) -> object:
        if current is session:
            events.append(("prepare", kwargs))
        return original_prepare_check(current, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        ConfidenceLedgerSession,
        "prepare_check",
        _record_prepare_check,
    )

    def _stop_after_reservation(*args: object, **kwargs: object) -> object:
        del args, kwargs
        events.append(("compile", None))
        raise RuntimeError("stop_after_reservation")

    monkeypatch.setattr(
        promotion_sequence_module,
        "_compile_obligations",
        _stop_after_reservation,
    )

    with pytest.raises(RuntimeError, match="stop_after_reservation"):
        run_canonical_promotion_sequence(
            promotion_input,
            confidence_ledger_session=session,
        )

    assert [event for event, _ in events] == ["prepare", "prepare", "compile"]
    reservations = [payload for event, payload in events if event == "prepare"]
    assert all(isinstance(item, dict) for item in reservations)
    assert tuple(item["obligation_class"] for item in reservations) == (
        PromotionObligationClass.CALIBRATION,
        PromotionObligationClass.DATA,
    )
    assert tuple(item["instrument_id"] for item in reservations) == (
        "fixed_time_confidence_interval",
        "owner_verified_e_process",
    )
    assert tuple(item["certificate_ref"] for item in reservations) == (
        "s10://unit",
        "data-trust://unit",
    )


def test_n9_port_rebinds_every_adaptive_receipt_to_one_final_ledger_head(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        promotion_sequence_module,
        "_legacy_policy_promotion_callers",
        lambda repo_root: (),
    )
    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    problem_id = f"adaptive_ledger_{uuid4().hex}"
    from tests.unit.runtime.quality.test_generation_cycle import (
        _positive_epoch_admitted_batch,
        _problem,
    )

    problem = _problem(problem_id)
    first = _summary()
    second = first.model_copy(
        update={
            "candidate_id": "candidate_n9_second",
            "content_hash": _hash("8"),
        }
    )

    admitted_batch = _positive_epoch_admitted_batch(
        runtime=runtime,
        problem=problem,
        summaries=(first, second),
    )
    port = CanonicalN9PromotionPort(
        repo_root=REPO_ROOT,
        promotion_runtime=runtime,
        epoch_n9_evidence_resolver=runtime.epoch_n9_evidence_resolver,
    )
    assert port.epoch_validity_resolver is runtime.epoch_n9_evidence_resolver
    observation = port(admitted_batch=admitted_batch, problem=problem)
    receipts = tuple(
        CanonicalPromotionReceipt.model_validate(item) for item in observation.receipts
    )

    assert len(receipts) == 2
    assert len({item.confidence_ledger_head_id for item in receipts}) == 1
    assert len({item.confidence_ledger_receipt_id for item in receipts}) == 1
    check_refs = {item.risk_spend.spend_records[0].n11_confidence_ledger_ref for item in receipts}
    projected_check_refs = {
        row.check_id for row in receipts[0].confidence_ledger_projection.promotion_rows
    }
    assert len(check_refs) == 2
    assert check_refs <= projected_check_refs
    assert all(
        validate_canonical_promotion_receipt(
            item,
            open_world_resolver=port.open_world_resolver,
            epoch_validity_resolver=port.epoch_validity_resolver,
        )
        == ()
        for item in receipts
    )


def test_promotion_context_cannot_supply_open_world_gate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        promotion_sequence_module,
        "_legacy_policy_promotion_callers",
        lambda repo_root: (),
    )
    from tests.unit.runtime.quality.test_generation_cycle import (
        _positive_epoch_admitted_batch,
        _problem,
    )

    problem = _problem(f"open_world_context_{uuid4().hex}")
    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    admitted_batch = _positive_epoch_admitted_batch(
        runtime=runtime,
        problem=problem,
        summaries=(_summary(),),
    )
    port = CanonicalN9PromotionPort(
        context_provider=lambda summary, owner_problem: {
            "open_world_gate": (summary, owner_problem)
        },
        promotion_runtime=runtime,
        epoch_n9_evidence_resolver=runtime.epoch_n9_evidence_resolver,
        repo_root=REPO_ROOT,
    )
    assert port.epoch_validity_resolver is runtime.epoch_n9_evidence_resolver

    with pytest.raises(ValueError, match="promotion_context_cannot_supply_open_world_gate"):
        port(admitted_batch=admitted_batch, problem=problem)


@pytest.mark.parametrize("legacy_field", ["admissibility", "effective_independence"])
def test_promotion_context_cannot_supply_legacy_gate_predicate(
    legacy_field: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        promotion_sequence_module,
        "_legacy_policy_promotion_callers",
        lambda repo_root: (),
    )
    from tests.unit.runtime.quality.test_generation_cycle import (
        _positive_epoch_admitted_batch,
        _problem,
    )

    problem = _problem(f"legacy_gate_context_{legacy_field}_{uuid4().hex}")
    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    admitted_batch = _positive_epoch_admitted_batch(
        runtime=runtime,
        problem=problem,
        summaries=(_summary(),),
    )
    port = CanonicalN9PromotionPort(
        context_provider=lambda summary, owner_problem: {legacy_field: (summary, owner_problem)},
        promotion_runtime=runtime,
        epoch_n9_evidence_resolver=runtime.epoch_n9_evidence_resolver,
        repo_root=REPO_ROOT,
    )

    with pytest.raises(ValueError, match="promotion_context_cannot_supply_gate_predicate"):
        port(admitted_batch=admitted_batch, problem=problem)


def test_absent_open_world_runtime_freezes_production_promotion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        promotion_sequence_module,
        "_legacy_policy_promotion_callers",
        lambda repo_root: (),
    )
    problem_id = f"missing_open_world_runtime_{uuid4().hex}"
    problem = SimpleNamespace(
        design_problem_id=problem_id,
        model_spec_ref=None,
        schema_version="policyos.runtime.design_problem.test.v1",
        model_dump=lambda **kwargs: {
            "design_problem_id": problem_id,
            "schema_version": "policyos.runtime.design_problem.test.v1",
        },
    )

    result = CanonicalN9PromotionPort(repo_root=REPO_ROOT)(
        admitted_batch=None,  # type: ignore[arg-type]
        problem=problem,  # type: ignore[arg-type]
    )

    assert result.status == "not_promoted"
    assert result.receipts == ()
    assert result.reason == "epoch_validity_refused:promotion_runtime_not_established"


def test_verification_port_never_certifies_candidates() -> None:
    problem_id = f"verification_port_{uuid4().hex}"
    problem = SimpleNamespace(
        design_problem_id=problem_id,
        model_spec_ref=None,
        schema_version="policyos.runtime.design_problem.test.v1",
        model_dump=lambda **kwargs: {
            "design_problem_id": problem_id,
            "schema_version": "policyos.runtime.design_problem.test.v1",
        },
    )
    binding = N9DesignProblemBinding.from_problem(problem)  # type: ignore[arg-type]
    session = _verification_ledger_session(binding=binding)
    port = CanonicalN9PromotionPort._for_verification(
        repo_root=REPO_ROOT,
        confidence_ledger_session=session,
    )

    observation = port(summaries=(_summary(),), problem=problem)  # type: ignore[arg-type]
    receipt = CanonicalPromotionReceipt.model_validate(observation.receipts[0])

    assert observation.status == "not_promoted"
    assert observation.certified_candidate_ids == ()
    assert receipt.confidence_ledger_projection.authority_provenance == "verification"
    assert receipt.consumer_promotable is False
    assert receipt.non_promotable_reason == "verification_only_replay"


def test_verification_port_requires_loaded_repo_for_non_ledger_owners(
    tmp_path: Path,
) -> None:
    session = _verification_ledger_session()

    with pytest.raises(ValueError, match="verification_owner_repo_root_invalid"):
        CanonicalN9PromotionPort._for_verification(
            repo_root=tmp_path,
            confidence_ledger_session=session,
        )


@pytest.mark.parametrize(
    ("kwarg", "value"),
    [
        ("confidence_ledger_session_factory", lambda _problem: _ledger_session()),
        (
            "confidence_ledger_artifact_store",
            FileSystemCAS(REPO_ROOT / ".tmp" / "gy-n11-forbidden-cas"),
        ),
        (
            "confidence_ledger_state_root",
            REPO_ROOT / ".tmp" / "gy-n11-forbidden-state",
        ),
    ],
)
def test_n9_port_exposes_no_custom_ledger_namespace_injection(
    kwarg: str,
    value: object,
) -> None:
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        CanonicalN9PromotionPort(**{kwarg: value})  # type: ignore[arg-type]


def test_n9_port_rejects_epoch_resolver_from_another_runtime(tmp_path: Path) -> None:
    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "owner-cas"))
    foreign = PromotionRuntime(store=FileSystemCAS(tmp_path / "foreign-cas"))

    with pytest.raises(ValueError, match="epoch_n9_evidence_resolver_owner_mismatch"):
        CanonicalN9PromotionPort(
            promotion_runtime=runtime,
            epoch_n9_evidence_resolver=foreign.epoch_n9_evidence_resolver,
            repo_root=REPO_ROOT,
        )


def test_probabilistic_certificate_bypassing_ledger_is_rejected() -> None:
    receipt = _run(_promotion_input())
    calibration = _obligation(receipt, PromotionObligationClass.CALIBRATION)
    bypass = calibration.model_copy(
        update={
            "status": PromotionObligationStatus.SATISFIED,
            "reason": None,
            "risk_spend": None,
            "detail": "forged fixed-time certificate bypassed N11",
        }
    )
    obligations = tuple(
        bypass if item.obligation_class == PromotionObligationClass.CALIBRATION else item
        for item in receipt.obligations
    )
    edited = receipt.model_copy(
        update={
            "obligations": obligations,
            "gate_outcome_hash": _gate_outcome_hash(obligations),
        }
    )

    issues = validate_canonical_promotion_receipt(edited)

    assert "probabilistic_certificate_bypassed_confidence_ledger" in {
        issue["code"] for issue in issues
    }


def test_non_calibration_probabilistic_certificate_bypass_is_rejected() -> None:
    receipt = _run(_promotion_input())
    data = _obligation(receipt, PromotionObligationClass.DATA)
    bypass = data.model_copy(
        update={
            "status": PromotionObligationStatus.SATISFIED,
            "reason": None,
            "risk_spend": None,
            "detail": "forged sibling probabilistic certificate bypassed N11",
        }
    )
    obligations = tuple(
        bypass if item.obligation_class == PromotionObligationClass.DATA else item
        for item in receipt.obligations
    )
    edited = receipt.model_copy(
        update={
            "obligations": obligations,
            "gate_outcome_hash": _gate_outcome_hash(obligations),
        }
    )

    issues = validate_canonical_promotion_receipt(edited)

    assert "probabilistic_certificate_bypassed_confidence_ledger" in {
        issue["code"] for issue in issues
    }


def test_rehashed_owner_outcome_relabel_is_rejected_by_owner_recomputation() -> None:
    receipt = _run(_promotion_input(g4_governed_promotion_ref="pdc://forged/g4/not-resolved"))
    obligations = tuple(
        obligation.model_copy(
            update={
                "status": PromotionObligationStatus.SATISFIED,
                "reason": None,
                "semantic_scope": "real_semantics",
            }
        )
        if obligation.obligation_role == "class_gate"
        and obligation.obligation_class == PromotionObligationClass.PARAM
        else obligation
        for obligation in receipt.obligations
    )
    edited = receipt.model_copy(
        update={
            "obligations": obligations,
            "gate_outcome_hash": _gate_outcome_hash(obligations),
            "refusal_reasons": tuple(
                reason for reason in receipt.refusal_reasons if not reason.startswith("param:")
            ),
        }
    )

    issues = validate_canonical_promotion_receipt(edited)

    assert "promotion_owner_recomputation_drift" in {issue["code"] for issue in issues}


def test_rehashed_computed_boundary_is_rejected_by_owner_recomputation() -> None:
    receipt = _run(_promotion_input())
    boundary = receipt.computed_authority_boundary.model_copy(
        update={"boundary_id": "n9.forged.rehashed.boundary"}
    )
    edited = receipt.model_copy(update={"computed_authority_boundary": boundary})

    issues = validate_canonical_promotion_receipt(edited)

    assert "promotion_owner_recomputation_drift" in {issue["code"] for issue in issues}


def test_rehashed_contract_lane_as_production_is_rejected_by_owner_recomputation() -> None:
    receipt = _run(_promotion_input())
    refusal_reasons = promotion_sequence_module._refusal_reasons(
        receipt.obligations,
        risk_spend=receipt.risk_spend,
        allow_non_authoritative_contract_scope_gaps=False,
    )
    edited = receipt.model_copy(
        update={
            "promotion_lane": "production",
            "refusal_reasons": tuple(refusal_reasons),
        }
    )

    issues = validate_canonical_promotion_receipt(edited)

    assert "promotion_refusal_reasons_drift" in {issue["code"] for issue in issues}


def test_receipt_candidate_id_must_match_replayed_owner_input() -> None:
    receipt = _run(_promotion_input())
    edited = receipt.model_copy(update={"candidate_id": "candidate_forged_replay"})

    issues = validate_canonical_promotion_receipt(edited)

    assert "promotion_owner_recomputation_drift" in {issue["code"] for issue in issues}


def test_rehashed_owner_projection_still_fails_live_candidate_binding() -> None:
    receipt = _run(_promotion_input())
    sibling = receipt.owner_projection.candidate_summary.model_copy(
        update={
            "candidate_id": "candidate_sibling_replay",
            "content_hash": _hash("6"),
        }
    )
    projection_payload = receipt.owner_projection.model_dump(
        mode="json",
        exclude={"projection_hash"},
    )
    projection_payload["candidate_summary"] = sibling.model_dump(mode="json")
    projection_payload["projection_hash"] = gy_content_hash(projection_payload)
    owner_projection = type(receipt.owner_projection).model_validate(projection_payload)
    edited = receipt.model_copy(
        update={
            "owner_projection": owner_projection,
            "candidate_id": sibling.candidate_id,
        }
    )

    issues = validate_canonical_promotion_receipt(
        edited,
        candidate_summary=receipt.owner_projection.candidate_summary,
    )

    assert "promotion_candidate_owner_binding_invalid" in {issue["code"] for issue in issues}


def test_empty_ledger_projection_cannot_insure_forged_probabilistic_success() -> None:
    promotion_input = _promotion_input()
    receipt_session = _verification_ledger_session(binding=promotion_input.design_problem_binding)
    receipt = promotion_sequence_module._run_canonical_promotion_sequence_for_verification(
        promotion_input,
        confidence_ledger_session=receipt_session,
    )
    empty_session = _verification_ledger_session(binding=promotion_input.design_problem_binding)
    empty_ledger = empty_session.receipt()
    empty_projection = project_n9_promotion_certificate(
        empty_ledger,
        session=empty_session,
    )
    risk_spend = promotion_sequence_module._risk_spend_summary((), empty_projection)
    calibration = _obligation(receipt, PromotionObligationClass.CALIBRATION)
    forged_calibration = calibration.model_copy(
        update={
            "status": PromotionObligationStatus.SATISFIED,
            "reason": None,
            "risk_spend": None,
            "detail": "forged probabilistic success with an empty N11 projection",
        }
    )
    obligations = tuple(
        forged_calibration
        if item.obligation_class == PromotionObligationClass.CALIBRATION
        else item
        for item in receipt.obligations
    )
    gate_hash = _gate_outcome_hash(obligations)
    trace = promotion_sequence_module._authority_derivation_trace(
        promotion_input,
        obligations=obligations,
        boundary=receipt.computed_authority_boundary,
        gate_hash=gate_hash,
        risk_spend=risk_spend,
        confidence_ledger_receipt=empty_ledger,
        confidence_ledger_projection=empty_projection,
    )
    trace_hash = recompute_authority_trace_hash(trace)
    trace = trace.model_copy(update={"trace_content_hash": trace_hash})
    edited = receipt.model_copy(
        update={
            "status": "grounded_partial_admissible",
            "promoted": True,
            "terminal_kind": SearchTerminalKind.GROUNDED_PARTIAL_ADMISSIBLE,
            "obligations": obligations,
            "risk_spend": risk_spend,
            "confidence_ledger_scope_ref": empty_projection.scope_id,
            "confidence_ledger_head_id": empty_projection.head_event_id,
            "confidence_ledger_head_ref": empty_projection.head_event_ref,
            "confidence_ledger_receipt_id": empty_projection.ledger_receipt_id,
            "confidence_ledger_projection": empty_projection,
            "authority_derivation_trace": trace,
            "gate_outcome_hash": gate_hash,
            "trace_content_hash": trace_hash,
            "refusal_reasons": (),
        }
    )

    issues = promotion_sequence_module._validate_canonical_promotion_receipt_for_verification(
        edited,
        repo_root=REPO_ROOT,
        confidence_ledger_session=empty_session,
    )

    assert "probabilistic_certificate_bypassed_confidence_ledger" in {
        issue["code"] for issue in issues
    }


def test_ledger_claim_scope_is_recomputed_from_candidate_owner() -> None:
    promotion_input = _promotion_input()
    canonical_session = _verification_ledger_session(binding=promotion_input.design_problem_binding)
    canonical = promotion_sequence_module._run_canonical_promotion_sequence_for_verification(
        promotion_input,
        confidence_ledger_session=canonical_session,
    )
    session = _verification_ledger_session(binding=promotion_input.design_problem_binding)
    expected_offers = promotion_sequence_module._promotion_certificate_offers(
        promotion_input,
        registry=session.registry,
    )
    expected = next(
        item
        for item in expected_offers
        if item.certificate_class == "n8_fixed_time_calibration_candidate"
    )
    wrong_claim = PredictableClaimSpec(
        claim_ref=expected.claim.claim_ref,
        null_ref=expected.claim.null_ref,
        claim_scope_ref="n9://candidate-summary/sha256:" + "9" * 64,
        data_window_ref=expected.claim.data_window_ref,
        certificate_role=expected.claim.certificate_role,
        claim_polarity=expected.claim.claim_polarity,
    )
    wrong_offers = tuple(
        item.model_copy(update={"claim": wrong_claim}) if item is expected else item
        for item in expected_offers
    )
    checks = promotion_sequence_module._execute_promotion_certificate_offers(
        session,
        wrong_offers,
    )
    ledger = session.receipt()
    projection = project_n9_promotion_certificate(ledger, session=session)
    risk_spend = promotion_sequence_module._risk_spend_summary(checks, projection)
    edited = canonical.model_copy(
        update={
            "risk_spend": risk_spend,
            "confidence_ledger_scope_ref": projection.scope_id,
            "confidence_ledger_head_id": projection.head_event_id,
            "confidence_ledger_head_ref": projection.head_event_ref,
            "confidence_ledger_receipt_id": projection.ledger_receipt_id,
            "confidence_ledger_projection": projection,
        }
    )

    issues = promotion_sequence_module._validate_canonical_promotion_receipt_for_verification(
        edited,
        repo_root=REPO_ROOT,
        confidence_ledger_session=session,
    )

    assert {(issue["code"], issue.get("reason")) for issue in issues} >= {
        (
            "promotion_expected_ledger_check_invalid",
            "promotion_expected_ledger_check_mismatch",
        )
    }


def test_failed_obligation_cannot_be_relabelled_into_decision_front() -> None:
    promotion_input = _promotion_input()
    session = _ledger_session(
        run_ref="ledger-run:n9-forged-decision",
        binding=promotion_input.design_problem_binding,
    )
    receipt = run_canonical_promotion_sequence(
        promotion_input,
        confidence_ledger_session=session,
    )
    obligations = tuple(
        obligation.model_copy(
            update={
                "status": PromotionObligationStatus.SATISFIED,
                "reason": None,
                "semantic_scope": "real_semantics",
            }
        )
        if obligation.status == PromotionObligationStatus.SCOPE_INSUFFICIENT
        else obligation
        for obligation in receipt.obligations
    )
    assert any(obligation.status == PromotionObligationStatus.FAILED for obligation in obligations)
    gate_hash = _gate_outcome_hash(obligations)
    trace = promotion_sequence_module._authority_derivation_trace(
        promotion_input,
        obligations=obligations,
        boundary=receipt.computed_authority_boundary,
        gate_hash=gate_hash,
        risk_spend=receipt.risk_spend,
        confidence_ledger_receipt=session.receipt(),
        confidence_ledger_projection=receipt.confidence_ledger_projection,
    )
    trace_hash = recompute_authority_trace_hash(trace)
    trace = trace.model_copy(update={"trace_content_hash": trace_hash})
    forged = receipt.model_copy(
        update={
            "obligations": obligations,
            "refusal_reasons": (),
            "promoted": True,
            "status": "grounded_partial_admissible",
            "terminal_kind": SearchTerminalKind.GROUNDED_PARTIAL_ADMISSIBLE,
            "promotion_lane": "production",
            "consumer_promotable": True,
            "non_promotable_reason": None,
            "authority_derivation_trace": trace,
            "trace_content_hash": trace_hash,
            "gate_outcome_hash": gate_hash,
        }
    )

    issue_codes = {
        issue["code"]
        for issue in validate_canonical_promotion_receipt(
            forged,
        )
    }
    promotion = PromotionPortObservation(
        status="certified_current_valid",
        certified_candidate_ids=(forged.candidate_id,),
        reason="forged decision fields",
        receipts=(forged.model_dump(mode="json"),),
    )
    summaries = _apply_promotion_to_summaries(
        (promotion_input.candidate_summary,),
        promotion,
    )

    assert {
        "promotion_refusal_reasons_drift",
        "promotion_promoted_drift",
        "promotion_status_drift",
        "promotion_terminal_kind_drift",
        "promotion_consumer_promotable_drift",
        "promotion_trace_presence_drift",
    } <= issue_codes
    assert summaries[0].front == "research"
    assert summaries[0].certified_by_n9 is False


def test_promotion_history_rule_stays_v3_and_current_v5_requires_full_reissue() -> None:
    from tools.quality.validation import check_layer3_gy_promotion_contract as validator

    frozen = json.loads((REPO_ROOT / validator.OUTPUT_PATH).read_text(encoding="utf-8"))
    live, plan = validator._build_payload_with_comparison_plan(REPO_ROOT)
    receipt_keys = (
        "contract_lane_anytime_refusal",
        "production_honest_shadow",
        "non_promotable_contract_stamp",
    )
    for key in receipt_keys:
        frozen_receipt = promotion_sequence_module.parse_canonical_promotion_history_receipt(
            frozen[key]
        )
        live_receipt = CanonicalPromotionReceipt.model_validate(live[key])
        assert frozen_receipt.schema_version == (
            promotion_sequence_module.GY_PROMOTION_SEQUENCE_SCHEMA_VERSION
        )
        with pytest.raises(ValueError, match="schema_version"):
            CanonicalPromotionReceipt.model_validate(frozen[key])
        with pytest.raises(
            ValueError,
            match="legacy_open_world_gate_authority_not_admitted",
        ):
            promotion_sequence_module.canonical_promotion_receipt_semantic_projection(frozen[key])
        assert gy_recorded_content_hash(
            frozen_receipt.model_dump(mode="json")
        ) != gy_recorded_content_hash(live_receipt.model_dump(mode="json"))
        historical_projection = (
            promotion_sequence_module._canonical_promotion_receipt_v3_semantic_projection(
                frozen[key]
            )
        )
        assert historical_projection["schema_version"].endswith(".v3")
        assert "open_world_gate" not in historical_projection["owner_projection"]
        live_projection = promotion_sequence_module.canonical_promotion_receipt_semantic_projection(
            live_receipt.model_dump(mode="json")
        )
        assert set(live_projection) == (
            set(CanonicalPromotionReceipt.model_fields)
            - promotion_sequence_module._PROMOTION_RECEIPT_LINEAGE_FIELDS
        )
        assert set(live_projection["owner_projection"]) == (
            set(promotion_sequence_module.CanonicalPromotionOwnerProjection.model_fields)
            - promotion_sequence_module._PROMOTION_OWNER_PROJECTION_LINEAGE_FIELDS
        )
        assert set(live_projection["confidence_ledger_projection"]) == (
            set(promotion_sequence_module.N9PromotionCertificateProjection.model_fields)
            - promotion_sequence_module._PROMOTION_CERTIFICATE_LINEAGE_FIELDS
        )

    assert validator._comparison_identity_issues(frozen) == []
    live.pop("capture_wall_time_seconds", None)
    validator._set_comparison_identity(live, plan)
    live["contract_content_hash"] = validator._contract_content_hash(live)
    with pytest.raises(ValueError, match="promotion_comparison_admission_manifest_drift"):
        validator._reconcile_frozen_contract(REPO_ROOT, live, plan)


def test_self_rehashed_detached_n9_projection_cannot_mint_comparison_admission() -> None:
    promotion_input = _promotion_input()
    risk_scope = promotion_sequence_module.confidence_risk_scope_for_problem(
        promotion_input.design_problem_binding
    )
    with TemporaryDirectory(prefix="gy-n9-comparison-admission-") as temp_dir:
        state_root = Path(temp_dir)
        session = ConfidenceLedgerSession._for_verification(
            REPO_ROOT,
            risk_scope=risk_scope,
            artifact_store=FileSystemCAS(state_root / "cas"),
            state_root=state_root / "state",
        )
        receipt = promotion_sequence_module._run_canonical_promotion_sequence_for_verification(
            promotion_input,
            confidence_ledger_session=session,
        )
        proof = promotion_sequence_module.prove_canonical_promotion_receipt_for_comparison(
            receipt,
            repo_root=REPO_ROOT,
            confidence_ledger_session=session,
        )
        admission = promotion_sequence_module.canonical_promotion_comparison_admission_from_proof(
            proof
        )
        assert admission.source_content_hash == gy_recorded_content_hash(
            receipt.model_dump(mode="json")
        )
        forged_public_token = GyComparisonAdmission(
            owner_rule=admission.owner_rule,
            source_content_hash=admission.source_content_hash,
            projector=admission.projector,
            action=admission.action,
            predicate_provenance=admission.predicate_provenance,
        )
        with pytest.raises(AttributeError):
            proof._admission = forged_public_token
        assert (
            promotion_sequence_module.canonical_promotion_comparison_admission_from_proof(proof)
            is admission
        )
        with pytest.raises(
            ValueError,
            match="canonical_promotion_comparison_proof_invalid",
        ):
            promotion_sequence_module.canonical_promotion_comparison_admission_from_proof(
                forged_public_token
            )

        forged_payload = receipt.model_dump(mode="json")
        projection = forged_payload["confidence_ledger_projection"]
        projection["deployment_identity"] = "policy-engine-deployment:sha256:" + "f" * 64
        projection["projection_hash"] = gy_content_hash(
            {key: value for key, value in projection.items() if key != "projection_hash"}
        )
        forged = CanonicalPromotionReceipt.model_validate(forged_payload)
        with pytest.raises(ValueError, match="confidence_ledger_projection_drift"):
            promotion_sequence_module.admit_canonical_promotion_receipt_for_comparison(
                forged,
                repo_root=REPO_ROOT,
                confidence_ledger_session=session,
            )


def test_n9_semantic_ledger_changes_with_governing_owner_input() -> None:
    """The verification projection retains claim and filtration semantics."""

    baseline_input = _promotion_input()
    changed_input = baseline_input.model_copy(
        update={
            "candidate_summary": baseline_input.candidate_summary.model_copy(
                update={"content_hash": _hash("9")}
            )
        }
    )
    receipts: list[CanonicalPromotionReceipt] = []
    sessions: list[ConfidenceLedgerSession] = []
    for promotion_input in (baseline_input, changed_input):
        session = _verification_ledger_session(binding=promotion_input.design_problem_binding)
        sessions.append(session)
        receipts.append(
            promotion_sequence_module._run_canonical_promotion_sequence_for_verification(
                promotion_input,
                confidence_ledger_session=session,
            )
        )

    baseline_semantic = receipts[0].confidence_ledger_semantic_projection
    changed_semantic = receipts[1].confidence_ledger_semantic_projection
    assert baseline_semantic is not None
    assert changed_semantic is not None
    baseline_rows = {
        (row.obligation_class, row.certificate_ref): row for row in baseline_semantic.checks
    }
    changed_rows = {
        (row.obligation_class, row.certificate_ref): row for row in changed_semantic.checks
    }
    assert set(baseline_rows) == set(changed_rows)
    assert all(
        baseline_rows[key].claim_execution_projection_hash
        != changed_rows[key].claim_execution_projection_hash
        for key in baseline_rows
    )

    changed_proof = promotion_sequence_module.prove_canonical_promotion_receipt_for_comparison(
        receipts[1],
        repo_root=REPO_ROOT,
        confidence_ledger_session=sessions[1],
    )
    changed_admission = (
        promotion_sequence_module.canonical_promotion_comparison_admission_from_proof(changed_proof)
    )
    changed_payload = receipts[1].model_dump(mode="json")
    changed_plan = build_gy_comparison_projection_plan(
        changed_payload,
        admissions=(changed_admission,),
    )
    with pytest.raises(ValueError, match="promotion_legacy_comparison_semantic_mismatch"):
        changed_plan.preserve_admitted_blocks(
            receipts[0].model_dump(mode="json"),
            changed_payload,
        )


def test_runtime_admission_proxy_cannot_fabricate_second_deployment_lineage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A monkeypatched runtime identity is not a second verified deployment."""

    promotion_input = _promotion_input()
    baseline_session = _verification_ledger_session(binding=promotion_input.design_problem_binding)
    baseline = promotion_sequence_module._run_canonical_promotion_sequence_for_verification(
        promotion_input,
        confidence_ledger_session=baseline_session,
    )

    admit_loaded_runtime = confidence_ledger_module._admit_loaded_runtime

    def _admit_alternate_deployment(repo_root: Path) -> tuple[object, object, str]:
        baseline_value, quick_fence, _ = admit_loaded_runtime(repo_root)
        return (
            baseline_value,
            quick_fence,
            "policy-engine-deployment:sha256:" + "9" * 64,
        )

    monkeypatch.setattr(
        confidence_ledger_module,
        "_admit_loaded_runtime",
        _admit_alternate_deployment,
    )
    with pytest.raises(ConfidenceLedgerError, match="canonical_loaded_runtime_mismatch"):
        _verification_ledger_session(binding=promotion_input.design_problem_binding)

    assert baseline.confidence_ledger_semantic_projection is not None


def test_promotion_comparison_repairs_current_v5_lineage_only_through_live_owner_proof() -> None:
    """Current v5 custody gains semantic lineage only from the live owner."""

    promotion_input = _promotion_input()
    session = _verification_ledger_session(binding=promotion_input.design_problem_binding)
    receipt = promotion_sequence_module._run_canonical_promotion_sequence_for_verification(
        promotion_input,
        confidence_ledger_session=session,
    )
    proof = promotion_sequence_module.prove_canonical_promotion_receipt_for_comparison(
        receipt,
        repo_root=REPO_ROOT,
        confidence_ledger_session=session,
    )
    admission = promotion_sequence_module.canonical_promotion_comparison_admission_from_proof(proof)
    current = {"receipt": receipt.model_dump(mode="json")}
    legacy = deepcopy(current)
    legacy_receipt = legacy["receipt"]
    semantic = legacy_receipt.pop("confidence_ledger_semantic_projection")
    raw_rows = deepcopy(legacy_receipt["confidence_ledger_projection"]["promotion_rows"])
    plan = build_gy_comparison_projection_plan(current, admissions=(admission,))

    with pytest.raises(ValueError, match="promotion_comparison_semantic_ledger_missing"):
        plan.project(legacy)
    migrated = plan.preserve_admitted_blocks(legacy, current)

    assert migrated["receipt"]["confidence_ledger_projection"]["promotion_rows"] == raw_rows
    assert migrated["receipt"]["confidence_ledger_semantic_projection"] == semantic
    assert plan.project(migrated) == plan.project(current)

    forged_legacy = deepcopy(legacy)
    forged_legacy["receipt"]["owner_projection"]["candidate_summary"]["content_hash"] = _hash("f")
    with pytest.raises(ValueError, match="promotion_legacy_comparison_semantic_mismatch"):
        plan.preserve_admitted_blocks(forged_legacy, current)


def test_promotion_comparison_refuses_v2_without_open_world_owner_fact() -> None:
    promotion_input = _promotion_input()
    session = _verification_ledger_session(binding=promotion_input.design_problem_binding)
    receipt = promotion_sequence_module._run_canonical_promotion_sequence_for_verification(
        promotion_input,
        confidence_ledger_session=session,
    )
    proof = promotion_sequence_module.prove_canonical_promotion_receipt_for_comparison(
        receipt,
        repo_root=REPO_ROOT,
        confidence_ledger_session=session,
    )
    admission = promotion_sequence_module.canonical_promotion_comparison_admission_from_proof(proof)
    current = {"receipt": receipt.model_dump(mode="json")}
    legacy = deepcopy(current)
    legacy_receipt = legacy["receipt"]
    legacy_receipt["schema_version"] = "policyos.policy_design_case.layer3_gy.n9_promotion.v2"
    legacy_owner = legacy_receipt["owner_projection"]
    legacy_owner["schema_version"] = "policyos.policy_design_case.layer3_gy.n9_owner_projection.v1"
    legacy_owner.pop("open_world_gate")
    legacy_owner.pop("epoch_validity_projection")
    legacy_owner["effective_independence"] = True
    legacy_owner["admissibility"] = True
    legacy_owner["projection_hash"] = gy_content_hash(
        {key: value for key, value in legacy_owner.items() if key != "projection_hash"}
    )
    identity_fields = {
        "obligation_role",
        "source_obligation_ref",
        "source_obligation_content_hash",
        "instance_scope_content_hash",
        "identity_provenance",
        "obligation_instance_id",
    }
    legacy_receipt["obligations"] = [
        {key: value for key, value in row.items() if key not in identity_fields}
        for row in legacy_receipt["obligations"]
        if row["obligation_role"] == "class_gate"
    ]
    legacy_receipt["confidence_ledger_semantic_projection"] = None
    legacy_certificate = legacy_receipt["confidence_ledger_projection"]
    legacy_certificate["risk_scope"]["rule_ref"] = (
        "policyos.policy_design_case.layer3_gy.n9_promotion.v2"
    )
    legacy_certificate["projection_hash"] = confidence_ledger_module._content_hash(
        {key: value for key, value in legacy_certificate.items() if key != "projection_hash"}
    )
    plan = build_gy_comparison_projection_plan(current, admissions=(admission,))

    parsed = promotion_sequence_module.parse_canonical_promotion_history_receipt(legacy_receipt)
    assert parsed.schema_version.endswith(".v2")
    with pytest.raises(ValueError, match="promotion_legacy_comparison_semantic_mismatch"):
        plan.preserve_admitted_blocks(legacy, current)


def _ledger_session(
    *,
    run_ref: str = "ledger-run:n9-promotion-test",
    binding: N9DesignProblemBinding | None = None,
) -> ConfidenceLedgerSession:
    owner_binding = binding or _problem_binding(run_ref=run_ref)
    risk_scope = ConfidenceRiskBudgetScope(
        scope_owner_ref=promotion_sequence_module.PROMOTION_SEQUENCE_REF,
        authority_purpose="n9_promotion",
        owner_scope_key=f"design-problem:{owner_binding.design_problem_id}",
        owner_projection_hash=owner_binding.problem_content_hash,
        epoch_ref=None,
        model_ref=owner_binding.model_spec_ref,
        rule_ref=promotion_sequence_module.CANONICAL_PROMOTION_SEQUENCE_SCHEMA_VERSION,
        schema_ref=owner_binding.problem_schema_version,
    )
    return ConfidenceLedgerSession.from_repo(
        REPO_ROOT,
        risk_scope=risk_scope,
    )


def _verification_ledger_session(
    *,
    binding: N9DesignProblemBinding | None = None,
    registry_source: object | None = None,
    resolver: Callable[[ConfidenceLedgerCheck], OwnerCertificateEvidence] | None = None,
    verifier: Callable[[OwnerCertificateEvidence], OwnerCertificateVerification] | None = None,
) -> ConfidenceLedgerSession:
    state_base = Path(mkdtemp(prefix="gy-n11-confidence-ledger-"))
    owner_binding = binding or _problem_binding(run_ref="n9-verification")
    risk_scope = ConfidenceRiskBudgetScope(
        scope_owner_ref=promotion_sequence_module.PROMOTION_SEQUENCE_REF,
        authority_purpose="n9_promotion",
        owner_scope_key=f"design-problem:{owner_binding.design_problem_id}",
        owner_projection_hash=owner_binding.problem_content_hash,
        epoch_ref=None,
        model_ref=owner_binding.model_spec_ref,
        rule_ref=promotion_sequence_module.CANONICAL_PROMOTION_SEQUENCE_SCHEMA_VERSION,
        schema_ref=owner_binding.problem_schema_version,
    )
    return ConfidenceLedgerSession._for_verification(
        REPO_ROOT,
        risk_scope=risk_scope,
        artifact_store=FileSystemCAS(state_base / "cas"),
        state_root=state_base / "state",
        registry_source=registry_source,
        certificate_resolver=resolver,
        certificate_verifier=verifier,
    )


def _run(promotion_input: CanonicalPromotionInput) -> CanonicalPromotionReceipt:
    return run_canonical_promotion_sequence(
        promotion_input,
        confidence_ledger_session=_ledger_session(binding=promotion_input.design_problem_binding),
    )


def _promotion_input(**overrides: object) -> CanonicalPromotionInput:
    summary = overrides.pop("summary", _summary())
    value_receipt = overrides.pop("value_receipt", _value_receipt())
    reference, decision = _cg2_contract_bind()
    kwargs = {
        "design_problem_binding": overrides.pop(
            "design_problem_binding",
            _problem_binding(),
        ),
        "candidate_summary": summary,
        "value_receipt": value_receipt,
        "grounding_decision_certificate": decision,
        "credal_reference": reference,
        "s6_blind_spot_posture": _s6_posture(),
        "s7_delegation_posture": _s7_posture(),
        "s8_value_posture": _s8_posture(),
        "declared_authority_transform": {
            "requested_evidence_kind": "transport",
            "requested_decision_grade": "advisory_admissible",
        },
    }
    kwargs.update(overrides)
    return CanonicalPromotionInput(**kwargs)


def _legacy_v4_history_payload(receipt: CanonicalPromotionReceipt) -> dict[str, object]:
    """Project one current receipt into exact v4/v1 historical coordinates."""

    payload = deepcopy(receipt.model_dump(mode="json"))
    v4 = "policyos.policy_design_case.layer3_gy.n9_promotion.v4"
    v5 = "policyos.policy_design_case.layer3_gy.n9_promotion.v5"
    payload["schema_version"] = v4
    owner = payload["owner_projection"]
    assert isinstance(owner, dict)
    owner["schema_version"] = "policyos.policy_design_case.layer3_gy.n9_owner_projection.v2"
    owner["effective_independence"] = True
    owner["admissibility"] = True

    boundaries = [payload["computed_authority_boundary"]]
    for posture_name in ("s7_delegation_posture", "s8_value_posture"):
        posture = owner.get(posture_name)
        if isinstance(posture, dict) and isinstance(posture.get("authority_boundary"), dict):
            boundaries.append(posture["authority_boundary"])
    for boundary in boundaries:
        assert isinstance(boundary, dict)
        boundary["rule_version_refs"] = [
            v4 if item == v5 else item for item in boundary["rule_version_refs"]
        ]
    owner["projection_hash"] = gy_content_hash(
        {key: value for key, value in owner.items() if key != "projection_hash"}
    )

    binding = owner["design_problem_binding"]
    summary = owner["candidate_summary"]
    assert isinstance(binding, dict)
    assert isinstance(summary, dict)
    scope_hash = gy_content_hash(
        {
            "rule_version": "polisyos.policy_design_case.layer3_gy.n9_obligation_scope.v1",
            "promotion_rule_version": v4,
            "design_problem_id": binding["design_problem_id"],
            "problem_content_hash": binding["problem_content_hash"],
            "candidate_id": summary["candidate_id"],
            "candidate_content_hash": summary["content_hash"],
            "operation_invocation_id": owner["operation_invocation_id"],
        }
    )
    obligations: list[PromotionObligationRecord] = []
    for raw_row in payload["obligations"]:
        assert isinstance(raw_row, dict)
        row = PromotionObligationRecord.model_validate(raw_row)
        instance_id = promotion_obligation_instance_id(
            obligation_role=row.obligation_role,
            obligation_class=row.obligation_class,
            gate_id=row.gate_id,
            source_obligation_ref=row.source_obligation_ref,
            source_obligation_content_hash=row.source_obligation_content_hash,
            instance_scope_content_hash=scope_hash,
        )
        obligations.append(
            row.model_copy(
                update={
                    "instance_scope_content_hash": scope_hash,
                    "obligation_instance_id": instance_id,
                }
            )
        )
    payload["obligations"] = [row.model_dump(mode="json") for row in obligations]
    payload["gate_outcome_hash"] = _gate_outcome_hash(
        obligations,
        open_world_gate=receipt.owner_projection.open_world_gate,
        epoch_validity_projection=receipt.owner_projection.epoch_validity_projection,
    )

    projection = payload["confidence_ledger_projection"]
    assert isinstance(projection, dict)
    risk_scope = projection["risk_scope"]
    assert isinstance(risk_scope, dict)
    risk_scope["rule_ref"] = v4
    projection["projection_hash"] = confidence_ledger_module._content_hash(
        {key: value for key, value in projection.items() if key != "projection_hash"}
    )
    payload["confidence_ledger_semantic_projection"] = None
    return payload


def _current_receipt_with_v1_scope_rows(
    receipt: CanonicalPromotionReceipt,
) -> dict[str, object]:
    """Keep current outer bytes while restamping internally coherent v1 rows."""

    payload = deepcopy(receipt.model_dump(mode="json"))
    owner = payload["owner_projection"]
    assert isinstance(owner, dict)
    binding = owner["design_problem_binding"]
    summary = owner["candidate_summary"]
    assert isinstance(binding, dict)
    assert isinstance(summary, dict)
    scope_hash = gy_content_hash(
        {
            "rule_version": "polisyos.policy_design_case.layer3_gy.n9_obligation_scope.v1",
            "promotion_rule_version": receipt.schema_version,
            "design_problem_id": binding["design_problem_id"],
            "problem_content_hash": binding["problem_content_hash"],
            "candidate_id": summary["candidate_id"],
            "candidate_content_hash": summary["content_hash"],
            "operation_invocation_id": owner["operation_invocation_id"],
        }
    )
    obligations: list[PromotionObligationRecord] = []
    for raw_row in payload["obligations"]:
        assert isinstance(raw_row, dict)
        row = PromotionObligationRecord.model_validate(raw_row)
        instance_id = promotion_obligation_instance_id(
            obligation_role=row.obligation_role,
            obligation_class=row.obligation_class,
            gate_id=row.gate_id,
            source_obligation_ref=row.source_obligation_ref,
            source_obligation_content_hash=row.source_obligation_content_hash,
            instance_scope_content_hash=scope_hash,
        )
        obligations.append(
            row.model_copy(
                update={
                    "instance_scope_content_hash": scope_hash,
                    "obligation_instance_id": instance_id,
                }
            )
        )
    payload["obligations"] = [row.model_dump(mode="json") for row in obligations]
    payload["gate_outcome_hash"] = _gate_outcome_hash(
        obligations,
        open_world_gate=receipt.owner_projection.open_world_gate,
        epoch_validity_projection=receipt.owner_projection.epoch_validity_projection,
    )
    return payload


def _probabilistic_offer(
    obligation_class: PromotionObligationClass,
) -> PromotionCertificateOffer:
    return PromotionCertificateOffer(
        request_key=f"n9://candidate_n9/{obligation_class.value}/future-owner-e-process",
        certificate_class="n8_data_trust_promotion_candidate",
        certificate_ref=f"future-owner://{obligation_class.value}/certificate",
        owner_projection_hash="sha256:" + "8" * 64,
        claim=PredictableClaimSpec(
            claim_ref=f"n9://candidate/candidate_n9/{obligation_class.value}/promotion",
            null_ref=f"n9://null/{obligation_class.value}/not-promotion-valid",
            claim_scope_ref="n9://candidate-summary/future-owner-probe",
            data_window_ref="future-owner://data-window/frozen-before-check",
            certificate_role="promotion",
            claim_polarity="false_accept",
        ),
    )


def _problem_binding(
    *,
    run_ref: str = "n9-promotion-test",
) -> N9DesignProblemBinding:
    problem_id = f"n9_{uuid4().hex}"
    return N9DesignProblemBinding(
        design_problem_id=problem_id,
        problem_content_hash=gy_content_hash(
            {
                "design_problem_id": problem_id,
                "run_ref": run_ref,
                "schema_version": "policyos.runtime.design_problem.test.v1",
            }
        ),
        model_spec_ref=None,
        problem_schema_version="policyos.runtime.design_problem.test.v1",
    )


def _summary(
    *,
    current_valid: bool = True,
    grounding_status: str = "current_valid",
) -> CandidateSummary:
    return CandidateSummary(
        candidate_id="candidate_n9",
        content_hash=_hash("2"),
        cycle_index=0,
        generation_channel="n4_owner",
        proxy_score=0.2,
        voi_estimate=0.1,
        grounding_status=grounding_status,  # type: ignore[arg-type]
        grounding_source="cgf_firewall",
        grounding_disposition="shadow_bound",
        grounding_score=0.95,
        current_valid=current_valid,
        value_status="value_ready",
        value_decision_grade="high",
        value_ref=_hash("3"),
        front="research",
        high_proxy=False,
        low_grounding=False,
    )


def _open_world_gate(*, status: str, code: str) -> OpenWorldRiskPromotionGate:
    def ref(label: str, profile_record: str) -> core_artifacts.ArtifactRef:
        profile = c4_profile(profile_record)
        return core_artifacts.ArtifactRef(
            artifact_id=core_artifacts.ArtifactID(gy_content_hash({"label": label})),
            kind=profile.kind,
            media_type=profile.media_type,
        )

    return OpenWorldRiskPromotionGate(
        status=status,  # type: ignore[arg-type]
        limitation_code=code,
        vector_artifact_ref=ref("open-world-vector", "open_world_risk_vector"),
        raw_cas_hash=gy_content_hash({"label": "open-world-vector"}),
        semantic_hash=gy_content_hash({"label": "open-world-semantic"}),
        requested_query_context_ref=gy_content_hash({"label": "open-world-query"}),
        aggregate_context_ref=ref("open-world-aggregate", "aggregate_context"),
        aggregate_context_content_hash=gy_content_hash({"label": "open-world-aggregate-semantic"}),
        bound_member_ref=ref("open-world-member", "bound_member"),
        bound_member_content_hash=gy_content_hash({"label": "open-world-member-semantic"}),
        candidate_occurrence_ref=ref("open-world-occurrence", "candidate_occurrence"),
        candidate_occurrence_content_hash=gy_content_hash(
            {"label": "open-world-occurrence-semantic"}
        ),
        verifier_provenance_ref=core_artifacts.ArtifactRef(
            artifact_id=core_artifacts.ArtifactID(
                gy_content_hash({"label": "open-world-verifier"})
            ),
            kind="chronology.open_world_risk_verifier",
            media_type="text/plain",
        ),
        predicate_class="independently_reconciled",
    )


def _value_receipt(
    *,
    calibration_status: str = "pass",
    transport_status: str = "direct",
    method_fqn: str = "causal.inference.did.standard@1",
    representation: str = "interval_box",
) -> ValueGateReceipt:
    world_hash = _hash("4")
    data_trust = DataTrust(
        tier="unit",
        trust_cap=1.0,
        trust_multiplier=1.0,
        promotion_floor=0.5,
        authority_ref="data-trust://unit",
    )
    if representation == "scenario_set":
        value_set = ValueOuterSet(
            representation="scenario_set",
            identification_status="partial",
            assumption_status="externally_supported",
            data_trust=data_trust,
            world_model_record_ref=world_hash,
            epoch="2026",
            representation_status="certified",
        )
    else:
        value_set = ValueOuterSet.interval_box(
            coordinates=("welfare",),
            lower=(1.0,),
            upper=(1.0,),
            identification_mode="point",
            assumptions=(),
            assumption_status="externally_supported",
            calibration_scope={"scope": "unit"},
            data_trust=data_trust,
            world_model_record_ref=world_hash,
            epoch="2026",
            representation_status="certified",
        )
    return ValueGateReceipt(
        candidate_id="candidate_n9",
        evaluation_mode="simulate_only",
        selected_method_fqn=method_fqn,
        method_selection_trace=(method_fqn,),
        identification_status=value_set.identification_status,
        value_outer_set=value_set,
        transport_receipt=ValueTransportReceipt(
            status=transport_status,  # type: ignore[arg-type]
            world_model_record_id="wmr_n9",
            world_model_record_content_hash=world_hash,
            transport_result_ref="transport://unit",
            transport_status="identified" if transport_status != "blocked" else "blocked",
            transport_mode="direct",
            identification_engine="unit",
        ),
        calibration_receipt=ValueCalibrationReceipt(
            status=calibration_status,  # type: ignore[arg-type]
            forecast_tier="observable_calibrated",
            calibration_record_ref="s10://unit",
            issue_codes=() if calibration_status == "pass" else ("forecast_calibration_blocked",),
        ),
        world_model_record_id="wmr_n9",
        world_model_record_content_hash=world_hash,
        value_ref=_hash("3"),
        wall_time_ms=1.0,
        wmr_cache_status="built",
        k_world_ref_before=world_hash,
        k_world_ref_after=world_hash,
    )


def _cg2_contract_bind() -> tuple[CredalReference, object]:
    reference = _credal_reference()
    engine = GroundingRelationEngine(reference)
    cg1 = engine.certificate_for(_pure_synonym_probe(engine), proposal_id="n9-cg2-bind")
    decision = GroundingBindGate.for_contract_testing(
        reference,
        calibration_seed_anchor=True,
    ).certificate_for(cg1)
    payload = decision.model_dump(mode="json")
    safe_candidate = next(
        item
        for item in payload["safe_t"]["candidates"]
        if item["relation"] == "exact" and not item["is_adversarial_countercandidate"]
    )
    safe_candidate = {**safe_candidate, "safe": True, "reason": "contract_owner_bind"}
    safe_atom_id = str(safe_candidate["atom_id"])
    payload.update(
        {
            "decision": "bind",
            "decisive_reason": "bind_eligible",
            "selected_relation": "exact",
            "bound_atom_id": safe_atom_id,
            "closed_obligations": tuple(
                sorted(
                    {
                        *payload["closed_obligations"],
                        "unit_scale_consistent",
                    }
                )
            ),
            "open_obligations": (),
            "safe_t": {
                "safe_atom_ids": (safe_atom_id,),
                "candidates": (safe_candidate,),
                "robust_singleton": True,
            },
            "revalidation": {
                **payload["revalidation"],
                "replayed_selected_relation": "exact",
                "replayed_selected_atom_id": safe_atom_id,
                "selected_relation_reproduced": True,
                "selected_atom_reproduced": True,
            },
        }
    )
    payload["content_hash"] = recompute_grounding_decision_content_hash(payload)
    payload["certificate_id"] = f"cg2_cert_{payload['content_hash'].removeprefix('sha256:')[:16]}"
    return reference, GroundingDecisionCertificate.model_validate(payload)


def _boundary(*, grade: str = "decision_admissible") -> AuthorityBoundary:
    return AuthorityBoundary(
        boundary_id="n9.test.boundary",
        authoritative_for=["grounded_partial_admissible_policy_design"],
        may_not_use_for=["production_deployment"],
        source_authority="deterministic_producer",
        posture="governed",
        rule_version_refs=[promotion_sequence_module.CANONICAL_PROMOTION_SEQUENCE_SCHEMA_VERSION],
        evidence_kind="measurement",
        decision_grade=grade,  # type: ignore[arg-type]
    )


def _s6_posture() -> Layer2S6BlindSpotPostureInput:
    return Layer2S6BlindSpotPostureInput(
        overall_posture="clear_fail_closed",
        measurability_record_ref="s6://measure",
        aggregation_validity_record_ref="s6://aggregation",
        capacity_feasibility_record_ref="s6://capacity",
        mandate_legitimacy_record_ref="s6://mandate",
        strategic_response_record_ref="s6://strategic",
        system_dynamics_handoff_required=False,
        regime_reissue_required=False,
        limitation_summary="S6 clear for unit contract lane.",
        false_clear_penalty=0.0,
    )


def _s7_posture() -> Layer2S7DelegationPostureInput:
    now = datetime(2026, 7, 8, tzinfo=UTC)
    return Layer2S7DelegationPostureInput(
        delegation_contract_ref="s7://delegation",
        decision_rights_matrix_ref="s7://rights",
        human_decision_request_ref="s7://request",
        human_decision_record_ref="s7://decision",
        decision_class_id="governed_pilot",
        required_role="policy_owner",
        interaction_mode="recorded_decision",
        disposition="recorded_valid_decision",
        available_actions=["approve"],
        decision_action_exercised="approve",
        five_rights_requirement={"required": True},
        five_rights_check={"status": "pass"},
        value_stakes_impact="bounded",
        attention_cost_rank=1,
        responsibility_integrity_status="pass",
        mandate_record_ref="s6://mandate",
        s6_mandate_firewall_disposition="pass",
        requested_at=now,
        decided_at=now,
        voi_rank=1,
        authority_boundary=_boundary(),
        governed_pilot_eligible=True,
        limitation_summary="S7 valid governed-pilot decision.",
    )


def _s8_posture() -> Layer2S8ValuePostureInput:
    return Layer2S8ValuePostureInput(
        value_choice_provenance_ref="s8://value-choice",
        authorized_value_schedule_ref="s8://schedule",
        objective_function_provenance_ref="s8://objective",
        pareto_archive_ref="s8://pareto",
        value_tradeoff_disclosure_ref="s8://tradeoff",
        mandate_record_ref="s6://mandate",
        s6_mandate_firewall_disposition="pass",
        ranking_mode="ranked_with_authorized_values",
        disposition="authorized",
        p20_firewall_status="pass",
        p22_firewall_status="pass",
        value_provenance_completeness=1.0,
        value_authorization_decision_refs=["s8://decision"],
        handoff_rows=[{"handoff": "s8"}],
        limitation_summary="S8 authorized value posture.",
        authority_boundary=_boundary(),
    )


def _obligation(receipt: object, obligation_class: PromotionObligationClass):
    return next(
        item
        for item in receipt.obligations
        if item.obligation_role == "class_gate" and item.obligation_class == obligation_class
    )


def _credal_reference() -> CredalReference:
    edges = [
        _operator_edge("tax_relief_rate", minimum=0.0, maximum=0.5, unit="ratio"),
        _target_edge("tax_relief_rate", "global.tax_rate"),
        _lex_edge("tax_relief_statute", "tax_relief_rate"),
        _operator_edge("budget_allocation_multiplier", minimum=0.0, maximum=2.0, unit="ratio"),
        _target_edge("budget_allocation_multiplier", "government.balance"),
        _lex_edge("budget_law", "budget_allocation_multiplier"),
        _world_slot("global.tax_rate", unit="ratio"),
        _world_slot("government.balance", unit="usd"),
        _world_slot("household_cells.disposable_income", unit="usd"),
        _world_slot("household_cells.transfer_intensity", unit="ratio"),
        _policy_slot("tax_slot", "global.tax_rate"),
        _policy_slot("budget_slot", "government.balance"),
        _policy_slot("transfer_slot", "household_cells.transfer_intensity"),
    ]
    edge_index = {edge.key: edge for edge in edges}
    component_versions = {
        "L2": "unit-l2",
        "L3": "unit-l3",
        "L6": _component_hash(edges, prefix="L6_"),
        "WMR": "unit-wmr",
    }
    reference_hash = gy_content_hash(
        {
            "component_versions": component_versions,
            "edges": [edge.to_payload() for edge in sorted(edges, key=lambda item: item.key)],
        }
    )
    return CredalReference(
        schema_version=CREDAL_REFERENCE_SCHEMA_VERSION,
        reference_epoch=f"kref:{reference_hash.removeprefix('sha256:')[:16]}",
        reference_hash=reference_hash,
        as_of="2026-06-29",
        component_versions=component_versions,
        essential_edges=edge_index,
    )


def _operator_edge(
    op: str,
    *,
    minimum: float,
    maximum: float,
    unit: str,
) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality="L6_KNOB_OPERATOR",
        edge_id=op,
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                {
                    "operator_kind": op,
                    "parameter_domain": {
                        "kind": "range",
                        "max_value": maximum,
                        "min_value": minimum,
                        "unit": unit,
                        "value_type": "float",
                    },
                },
                "unit_test_operator",
            ),
        ),
        provenance={"owner": "L6", "source": "unit"},
    ).with_content_hash()


def _target_edge(op: str, target: str) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality="L6_KNOB_WORLD_SLOT",
        edge_id=op,
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                {
                    "operator_kind": op,
                    "target_world_slots": [target],
                    "world_model_record_id": "unit-wmr",
                },
                "unit_test_target",
            ),
        ),
        provenance={"owner": "L6", "source": "unit"},
    ).with_content_hash()


def _lex_edge(law_token: str, op: str) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality="L6_LEX_INTERVENTION_MAP",
        edge_id=law_token,
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                {"law_token": law_token, "knob_id": op},
                "unit_test_lex_map",
            ),
        ),
        provenance={"owner": "L6", "source": "unit"},
    ).with_content_hash()


def _world_slot(slot: str, *, unit: str) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality="WMR_WORLD_SLOT",
        edge_id=slot,
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion("fixed", {"world_slot": slot}, "unit_test_wmr_slot"),
        ),
        provenance={"owner": "WMR", "source": "unit"},
        unit=unit,
    ).with_content_hash()


def _policy_slot(policy_slot: str, world_slot: str) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality="WMR_POLICY_SLOT_MAP",
        edge_id=f"{policy_slot}:{world_slot}",
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                {"policy_slot": policy_slot, "world_slot": world_slot},
                "unit_test_policy_slot",
            ),
        ),
        provenance={"owner": "WMR", "source": "unit"},
    ).with_content_hash()


def _component_hash(edges: list[CredalReferenceEdge], *, prefix: str) -> str:
    return gy_content_hash(
        [
            edge.content_hash
            for edge in sorted(edges, key=lambda item: item.key)
            if edge.modality.startswith(prefix)
        ]
    )


def _tax_atom(engine: GroundingRelationEngine) -> object:
    return next(
        item
        for item in engine.reference_atoms
        if item.signature.op == "tax_relief_rate" and "global.tax_rate" in item.signature.X_do
    )


def _pure_synonym_probe(engine: GroundingRelationEngine) -> dict[str, object]:
    atom = _tax_atom(engine)
    signature = atom.signature.model_dump(mode="json")
    signature["op"] = "tax_credit_rate"
    signature["effect_path"] = [
        "tax_credit_rate",
        *list(atom.signature.X_do),
        *list(atom.signature.outcome),
    ]
    signature["modal_claims"] = {
        "NL": {
            "op": "tax_credit_rate",
            "target": atom.signature.X_do[0],
            "outcome": atom.signature.outcome[0],
            "estimand": atom.signature.estimand,
        },
        "L6": {"knob": "tax_relief_rate"},
        "do_AST": {"op": "tax_credit_rate", "target": atom.signature.X_do[0]},
        "method": {
            "treatment_op": "tax_credit_rate",
            "treatment_target": atom.signature.X_do[0],
            "outcome": atom.signature.outcome[0],
            "estimand": atom.signature.estimand,
        },
    }
    return {
        "raw_text": "levy credit-rate alias for the exact same tax relief do-query.",
        "signature": signature,
    }


def _hash(seed: str) -> str:
    return "sha256:" + seed * 64
