# Governed public record evidence identities

Snapshot of complete retained local outputs and probe scripts. Gate codes, scope, commands and
findings are in [the execution journal](../governed-public-record.md). A hash identifies evidence;
it does not turn a failed, synthetic or incomplete run into a pass. Source artifacts are cited
as tracked paths at their delivery commits in that journal, not copied into this index.

Every regular file under the following raw directories was read; pathlib recursion and an
independent `rg --files --hidden --no-ignore` enumeration were reconciled. The emitted index
receipt and later delivery receipts are outside this snapshot. Unreadable entries would stop
the index with code 3, never count as absent. No repository-wide or external-evidence claim.

Replay: `python3 docs/superpowers/journals/governed-public-record/raw/index_evidence.py` from
`policy-engine/`. Full actual input reads and named limits are emitted as JSON.

## `/Users/deniskopylov/polisyos/.worktrees/governed-public-record/policy-engine/docs/superpowers/journals/governed-public-record/raw`

| Relative evidence path | SHA-256 |
| --- | --- |
| `admission.json` | `ea846a5fc7440fe71fe7caa9adad3f8f9441161432467533493e91c7113d6f46` |
| `browser-check-final.txt` | `943040389f79d352cf111741f8123b1eb30a68a23517308df03532354bf40091` |
| `browser-check-scoped-final.txt` | `e745af2c3d8e5a19d22abbbfa4a2aacb26dcbb63628278a63a72b53a66e30a66` |
| `browser-check.cjs` | `6a4d7d9d66e55f7e7eb053d6ef4b5671aeea9fa9c8770e427daedcf7ffeb246c` |
| `browser-check.txt` | `1345b85677ee8b3641a70125c82410dcd599b1bc5ea51b0455248e5b81a11e1a` |
| `browser-desktop.png` | `23ed18039ff024c4a14883f896da79c6f576ba869b12d7d1af87e2c74ca4c35c` |
| `browser-mobile.png` | `a17719bc7bd28578646d844e96c99999a00d2592869b7e7b374ea710fa16ee3b` |
| `browser-unavailable.png` | `d559a190c1086543ab286dfff6d0e6121a9f582e6f97e07c12b8f38afdf28995` |
| `browser-vite.txt` | `8b9c8b6b1cd8505a0208bd0314fc6789961b298064170f45f7c8b752c4e4f594` |
| `claim-packet-snapshot-final.txt` | `39c86985069b058c04c0ef64c7be16727e51e7c8949efbbcfd8cbf13700681fb` |
| `claim-packet-snapshot-green.txt` | `beadbc51fd01963750d3f8a957f6b7c5346241a6b6caae88d7ec62ce37f756a0` |
| `claim-packet-snapshot-lint.txt` | `83eda69f4732a85693ccbbb252ad999d1ce42a75aca551a7564c1364c47b62dd` |
| `claim-packet-snapshot-red.txt` | `f558224f992e6c2c98fc8074b94997014ec6a4a7f4a655057549623cc653f9ef` |
| `client-facade-generate.txt` | `0a95b55edf4ca5a7bb40e90e77e24b06788e3d5fda9717569ed82efcd38ca9be` |
| `client-generate-final.txt` | `719e5e9cbcbf525a342d9a0295988db8374ba1c10d74a1650017b3c04a18df8a` |
| `client-generate.txt` | `253fa3f3f48f207a7b19565e1f53021cce6d5d273cf10b18c6d6c4fec827642d` |
| `context-gate-base.txt` | `b48413b4dd629900362ec73ca48785e6b661341b4ea73754d37139fda4c0123e` |
| `context-gate-denominator.json` | `c2e187232b57c73c2390a55a8e7253496bacccf37e944ee3277a28efb8e3f0b0` |
| `context-gate-denominator.py` | `b176c40ec996479c6e5d7d49f7f7b1d573d2af0d1d523cab2b2feeacc46e4d6b` |
| `context-gate-lane.txt` | `b48413b4dd629900362ec73ca48785e6b661341b4ea73754d37139fda4c0123e` |
| `dashboard-api-generate-final.txt` | `4a5729cfa7e594c8a3231e9433153fca3aaff7e3612ad6cfc6ed4cf610b31a19` |
| `dashboard-api-generate.txt` | `e36aa09f0cca2e0b9f28ad1fc1577331cc5949c85415dbcb19920ad7a37a2fc7` |
| `dashboard-facade-generate.txt` | `545d761256d3034a975f027a1be631071438b95734f38fdefaaa213387ea5955` |
| `dashboard-typecheck-1.txt` | `e286f0410eb008113d7d03bc28c64fad7b0ad8853321ce375d25592e8ceb3c48` |
| `dashboard-typecheck-final.txt` | `ffca2ba224794183275f3dcf6f833c466a9d5463eaf75650aeb58efc0070ebfd` |
| `dashboard-typecheck-replay.txt` | `e286f0410eb008113d7d03bc28c64fad7b0ad8853321ce375d25592e8ceb3c48` |
| `ds17-root-source-diagnostic-stderr.txt` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `ds17-root-source-diagnostic.json` | `eb0611bf13bd8f7f2069132415c9edb28a1017a38045705a3a430e95aa2b0180` |
| `ds17-source-diagnostic-stderr.txt` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `ds17-source-diagnostic.json` | `251122239274823840c4a235180e5a0697f873da9e6205e0621fe8be470097a3` |
| `epoch-chain-before-bound.txt` | `e36fa4d957b3033f4d193183a1c2d41171a95824cb197f7b69433c39866f6dc2` |
| `epoch_chain_falsifier.py` | `09f1cec9aef97612983a5729cb37c42ba1af6cbb501867c50fd710c492c1504c` |
| `facade-branch-readback.json` | `1b3606c9dc406249396a568dfcc75fbee4a3b806efceaf523f3ad0eb322706ce` |
| `facade-commit.txt` | `17b1bddf5dd4b08149fb512b32c16ca98ac50896e4df4e2ca3db1f0b80faeb5f` |
| `facade-http-replay.txt` | `eb27a136c18598aedc0e4f11e6893b614a04335a9faf3ec03433325d777e2663` |
| `facade-review-dependency-reads.txt` | `addce4f74b5abbc6a0dab2c423af236ebe144316b3f0b09fb7c82976b8a33c5f` |
| `facade-review-original-guard-failure.txt` | `04e7f9972ac21e5067f5e0c9c45c780d545376b43848e1096a8e52c4f5950845` |
| `facade-review-pinned-script.py` | `dacb4487f2cd719e5e46e00fba9f8be316c558abdebd40e9da1e3ba5802e798b` |
| `facade-review-receipt.json` | `b25b98537472477c689f72b0d366fa7cc7a87d217b26f156a6a9b444eb7310d6` |
| `facade-review-replay.py` | `2cae083d0eef874ef9dfd34e13fba92d1707620b3c07ab66c178ee2a7c9a1575` |
| `facade-review-script.py` | `a221571a4178c3316649a502a0852a603da80889ccc03ed10fa57feb7cf3cac3` |
| `facade-review-stdout.txt` | `cd9d94f7958545f79ee53c5356d099e5e108c579d407e2462cae169fadaf2e45` |
| `facade-ruff.txt` | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| `frontend-eslint-final.txt` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `frontend-final-tests.txt` | `2787e9431ea98db98bf0105492101610793ea92e1e5decfd17c1f94d7e02805b` |
| `frontend-format-final.txt` | `0f2c2253af3c4c4d9a5b8390322311e619a605c621ba027ad89ef47d01dc9546` |
| `guardrails-base.txt` | `49de9e40a129b691b24b67825e290cf487823bae8df4456c1dd1a82262426e46` |
| `guardrails-closeout.txt` | `9fa49e2a57ea7578043fb7d62548f19b0e0f0734b1ace31d1943d46686829e18` |
| `guardrails-final.txt` | `0cd1a04026211ffa2c616e1ca96670ae8c5080dc3cebf24077d17bc78817ff91` |
| `historical-admission-removal-probe-final.txt` | `506e854d0ab3baa506fc238629a40ccc308b5290e1c28f0607823ef1feb2bdcf` |
| `historical-admission-removal-probe.txt` | `55ffe1176e0346aa849188d79251279ab827351ab83fc23470be6cbe684f2284` |
| `historical-claim-red.txt` | `6d97a14f68c72a7ebc7bd69adad3abf8663e527fe6a95b38dd5dcbb64193d8db` |
| `historical-seam-absence.txt` | `1f33221ceacde3a09c934f26173125bd5dd065923a66112560ee511e6de95e85` |
| `historical_admission_removal_probe.py` | `04a6569b01af0081fd53571ca84090ed9d08c2fa8545c97e0c589c2138074d20` |
| `http-governed-first.txt` | `b7c74954c7d3d2b0ca5124fb284045885f3f18b2e3e9227d30d1631f35ad74ef` |
| `http-history-final-lint.txt` | `a84c6440d2cf0fe1f29b4cdca40b8fc2dabb8f20e8dfce2e791d572346ddc2f1` |
| `http-history-wave1.txt` | `319bd54db990e53c30d8de86154bc779af03c70af578d1d71d0676e8932d86e0` |
| `http-mandate-crypto-removal.txt` | `6edf21afd4b2d0312dea4e52a73257ab26488adbedf86ad0a0ca05a8a1671061` |
| `http-mandate-signature-negative.txt` | `34052cab7809d762a1e82750e5cf13d62ec501b8e35f9d853a711de07e918d6f` |
| `http-replay.txt` | `99db33d5c94c6f7da021687c7391181685cc33299c5435b1c861e2db3be3ec87` |
| `implementation-branch-readback.json` | `dfdf12d768ed291d2fa8bdb2d1a16e68c0e6061d54c55caae771af2676c04daa` |
| `index_evidence.py` | `b7ba0c7a09e031e1bffba143cbbf69e7069854ce83c3a14019ebf462c18f4c07` |
| `inventory-codec-diagnostic.txt` | `56f0e897ed7a09a416a46a7981618640ca79b2f057acfca6abdceed0f5e97309` |
| `inventory-codec-replay.txt` | `945fb98e574220bea1d52a3d8e33210585d12939469aec0847ce8e65b6fb6991` |
| `ledger-base.txt` | `5e6a8e2611c8cfbb1e9d56bcb454e55eec74a9aa4e57e4756291b3905680ac56` |
| `ledger-final.txt` | `6fe9d9db5b4e200e74b9efde1c982b4c23a29e4b080d68af8fd0ab1975ba1e7a` |
| `ledger-input-continuity.json` | `de38e530ed8adc9b2c276fbee10fdc81f36511b8333089353376abb0f1284005` |
| `ledger-input-continuity.py` | `ac8f7b57f433f0e237caf3b5e94d6cdfe32e025c7bba428e0176791a485b254f` |
| `legacy-integrated-1.txt` | `cfc14fd2dc11c362cccf5421245ca5ab0e9d286b54a604a80bd2dd5522f6feb9` |
| `openapi-facade-delta.json` | `a4e36ae68fe0bc2eff4c5ea44a6f86a48e5d8c257107a1ac9999f03e6fa6c241` |
| `openapi-facade-diagnostic.txt` | `2951742c4bd956a75fa61b6d861f10e4df19137d80921e212ddf87d095f44172` |
| `openapi-facade-frozen.txt` | `93836d486d8bac37754ee8f8c89d0985253d4359d58991f21b62f02d1661a05e` |
| `openapi-generate-final.txt` | `863d7abac7a56744f6af2c2834d0e9ddb03b35471d448d2f394cd04a9d6dc4b4` |
| `openapi-generate-frozen.txt` | `40e3d86e97843a41da4756a17d028101917563dcc826f1f0addd54f35680dacd` |
| `openapi-generate.txt` | `f486fb64ec6e731c1533cd4d1e9c098ca98f35cdf86cca39454f4f1477262773` |
| `openapi-refresh-commit.txt` | `bca49d38a0d2cccefd59454d1cee1a52fd205b4950c3d6ec9722b8d73bbc772b` |
| `openapi-refresh-readback.json` | `4589964951072929ebdd8a9b40937e2e65191a92d9f51db852849c3086b2f028` |
| `owner-final-file-receipt.json` | `e1f6a6e6cb605fe54aaa938cefe4ad79becd8e68d858ded0c9c3ec532e704f17` |
| `owner-final-file.txt` | `52849ffae8aa7e7baddd3ab7e290ef5c56863aeddf243502f8a51d171cbe976e` |
| `production-invocation.json` | `06f041ad573fc1ba685227ecf07cfc475bad1c1185728788055f017395ea896b` |
| `production-invocation.txt` | `a0f01efe9f82f4452eabeb5bd7b07b6ac5c6f726feb5f5a8cbe2e9f2e57dc584` |
| `public-facade-generation.txt` | `f2b818ee52ca048e22779b9ba94226290b799f04d6c6a8c8ee2354fa03342f5f` |
| `refusal-baseline.txt` | `bc4ecef6e102391f924f5ccd9439b9293755bd59b1519d7040a3233303f1745d` |
| `removal-probe.txt` | `fcb4dab6a7db39c617f006e3a06fbe24ee68d9c6ba21e7de3ba1294013f2f0f3` |
| `removal_probe.py` | `83421b00b42013a984d53160aed6a9720cbfcf197f058f6bf33dfc71da524307` |
| `replay-row-census.py` | `227a77dd6843345b52a4e6eb0f153c5fdc3372718970289c642373a9d34fd084` |
| `root-format.txt` | `18e6d980f3240b191032244b3052f2ba69c5625810c41885654eb7d5488ac1e1` |
| `root-ruff-final.txt` | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| `rows-lint-final.txt` | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| `rows-lint.txt` | `b4dccd1bc10844ba8086231abf68705c3280bf5272ed1bb03395bee65493606e` |
| `rows-stage1-final.json` | `a37445813544aa5f44864e55b968f1dd6b460018fd4d395283246ab16d0f5c62` |
| `rows-stage1-reviewed.json` | `a37445813544aa5f44864e55b968f1dd6b460018fd4d395283246ab16d0f5c62` |
| `rows-stage1.json` | `c032ea05309ba8f626f17bfaa90aafa5dee7b4fbd263b81386d00c613190335d` |
| `ruff-all-touched.txt` | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| `runtime-api-facade.openapi.json` | `5085bec3593692f6c46a55ec2a4549af73ff7cad880c9e818d58878afc0268b7` |
| `runtime-codec-replay.txt` | `f44919a3367dc52929a8af8f8919d5f9536d2eb90b5c6c6d38b1e58904be21bc` |
| `runtime-final.txt` | `b5cd33c6d4dfdcedf0d460dc02296ad0c188ec83185ea2057a399088bf1dbae9` |
| `stage1-preservation-readback.json` | `99fa9cfbe1a08f7c5c50f88eff25c9c2e9b0733a419f9202827a1d9d828269c5` |

## `/Users/deniskopylov/polisyos/.worktrees/governed-public-record/policy-engine/docs/superpowers/research/governed-public-record/raw`

| Relative evidence path | SHA-256 |
| --- | --- |
| `census-complete.json` | `b51664c766b9fd6e708e8525a73386d61d4bf917e3500732b96e44f8b328b567` |
| `census-deciding.json` | `759c06cf0e5e359f2c75d0ba94f317f876a8888d499d8bc43a98476e94b8ebc6` |
| `census-final-pinned.json` | `98cb658108996e4d7e884140588ec4fb7a87f492852730b27e56ce9839730a44` |
| `census-final.json` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `census-pinned.json` | `19596e55292737ee536bdebb1d927db9148b6c3f26d95b8b87b48ee9b01c1370` |
| `census-replay.json` | `a2acc6c21f317969d5f9ca0fee84d533eef4ca9da6cca5c4b651b49324c655f9` |
| `census.json` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `dependency-producer-index.txt` | `9bd21b85b9f7b20b9c2ef3f6d75439ca66e96f66dd1d0ccc078f3b32aba43c76` |
| `disposition-counts.json` | `0f59b54f917dbfdfe89e3ca3497e8c2a4b08b127fe68cfb96b3820bc81902429` |
| `fixture/inside.py` | `ce66b1366388342cfcafb7811fc7a250edc089c6ad973665a91a8cf25b8a9bbd` |
| `fixture/manifest.json` | `6b1d3999be26b21e36fbc6ade6a6b03277bd60c038c443608169a1c7c849e1eb` |
| `fixture/outside.md` | `3e99b89d713167517dfbd0a848ecc2f337b0f1034c9b656b4e376487b53ae657` |
| `negative-role-candidates.json` | `361b6657485485044ccdd5889e4f6d338c4ffe58f956f616d8131528ef52c120` |
| `negative-role-source-review.json` | `f2cc2ee8c1a0a795f1424e4031181f701493454809f8a9d47f5a150a94187511` |
| `negative-singletons-gitgrep.txt` | `3e5c30b4513cc2ecbcb1ac70aa5c5997d7d46c3a3e4e104eb45e3b04fdec98f9` |
| `owner-unit-wave-1.txt` | `8c741fc8614ce2667ce5e5d351d67c2e9cbafccaed235d54254a06ce9097c491` |
| `owner-unit-wave-2.txt` | `cfc14fd2dc11c362cccf5421245ca5ab0e9d286b54a604a80bd2dd5522f6feb9` |
| `owner-unit-wave-3.txt` | `c66ef7936b32d2201bf6eb901cf69cbc8e71996669c38afe1f70ad40098e04a3` |
| `probe-inside.json` | `b46ab2553ef8493e575acce99d4d61d55085d13a8c0c2d85616bd0ec6cf061f9` |
| `probe-outside-only.json` | `6015f200940b576e241566aef9042eed991aae8459986328152fca681e17bcba` |
| `probe-removed-property-kept-markers.json` | `7b07e5680131af14c6b8748f42d1c76ccbc15ad273e867fbc43333e4d2d4af1f` |
| `probe-summary.json` | `8b2e0017f7d32e4be7087b6a92e67e248a78280f5201b8254644e007b9f6e2ed` |
| `probe-unreadable.json` | `ec2d6c9ed2c72e875feab102b52dd145eb33afd5ea903e13129386df73995db6` |
| `public-record-search.txt` | `0e79860753c6fe47deef5c8d9d6869b629208ee3786aa4938c366ebaeaabec28` |
| `render-review.py` | `864964278818606d0c885b5017926c5eb633a92c48b4c78cc8c9a837b00af352` |
| `review-reconciliation.json` | `ce9c4cd235ce92f888fa531b2eac071eae7afa452987a0c75fe4b6a657384778` |
| `ruff-final.txt` | `ce04ce92b16073000b77c97a42c00b98b96305692d9d5ed4dcfa5a9ca9ea62d6` |
| `ruff-initial.txt` | `7f533fd27f8b64944d159c4a45abb7361c351d58c7ec75a09f84edd87751e118` |

## `/Users/deniskopylov/polisyos/.worktrees/raw/governed-public-record`

| Relative evidence path | SHA-256 |
| --- | --- |
| `admission.json` | `ea846a5fc7440fe71fe7caa9adad3f8f9441161432467533493e91c7113d6f46` |
| `environment-online.txt` | `2bbd46ab86d8f806a94955ce404d4cfc5e83ebdb461a43933f3ef9a6753b0281` |
| `environment.txt` | `1a8d8ac37e7d78a1f4ce2890ada52e0381641c548c01153a7d245857878b6db8` |
| `frontend-baseline.txt` | `ef3467d57918110c073bd007a817078e7cb366307f2b55213386e0769700fd77` |
| `frontend-eslint-final.txt` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `frontend-eslint.txt` | `6e932d5ab00bc73add7fa32e8aa4bafa77db9c59847b795818cc3d3c4b74cffd` |
| `frontend-format-check.txt` | `17aa973d3f004560237d9a95171210b0671deff23d61628eecf7322ff5938f20` |
| `frontend-format-final.txt` | `7182c0d243d2c225cd22077dd911844a76cb6f02cdce2a7670d608049ab44ce3` |
| `frontend-format.txt` | `9f0e88c346e773688c2c7968a7c26fb0660fb5256f6dd199679af996243ac4ac` |
| `frontend-positive-red.txt` | `a9e486d0c24edf97d14628fb84f36de049d3103329cb97065aa1aa8f39b20a59` |
| `frontend-route-tests-final.txt` | `b613862762d46605ff49c0c12df9e730266a821e38830cb2586863af00076b43` |
| `frontend-route-tests.txt` | `1eeb60569df0983cc33e911e0b125c64d46c2c7945f93234f0937e0f423bdc82` |
| `frontend-structured-eslint.txt` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `frontend-structured-format-check.txt` | `17aa973d3f004560237d9a95171210b0671deff23d61628eecf7322ff5938f20` |
| `frontend-structured-format.txt` | `a51e56db0dad585ab537036e86429c35df4038790cafefed638bc8b4cc1c4b69` |
| `frontend-structured-red.txt` | `12991e698f02756bfd1a3a764628defac0efa1f059476f0a2559a8e845bd6fa7` |
| `frontend-structured-tests.txt` | `a1bff6e9c38a25ab77ba53b435666b04d474079d3454bc9886a558b69aa290dd` |
| `pnpm.txt` | `c813171ed9d8c0d7555a987354c17dc448a7e7f462a2fe34026afbcd39ebc162` |
| `population-independent-format.txt` | `fd2299c9f1c6dc869070883e281051bfe93aacf66c1a3b0069f45b4aa410ca50` |
| `population-independent-ruff.txt` | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| `population-independent-tests.txt` | `99db33d5c94c6f7da021687c7391181685cc33299c5435b1c861e2db3be3ec87` |
| `public-contract-candidates.txt` | `796c61da1df4bf9518342da44f814951ea708e6aea686d5b0d63261d124952d2` |
