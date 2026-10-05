# F — Causal methods, graph, SCM, economics и Lex

Перед любой работой полностью прочитай как обязательные task instructions `policy-engine/docs/research/e02-cloud-test-plan/execution-prompts/HANDOFF.md` и корневой `AGENTS.md`. Ты — cloud root-оркестратор F. Прочитай `policy-engine/docs/research/e02-cloud-test-plan/results/README.md`; запроси `python3 policy-engine/docs/research/e02-cloud-test-plan/results/query.py --unit F --failures-only --limit 30`, затем конкретные cells и finding owner. Сверь source SHA, backend/markers и полноту входов; test skip/error не трактуй как PASS.

Владей `CAU, GRF, SCM, API, FRY, ECO, LEX, FIT`: 17 пакетов, 35 finding. Начни с двух writers по разным механизмам; до четырёх — только по непересекающимся owners. Строй analytic/DGP/graph negative controls рано и недорого; при изменении estimator запускай релевантные методологические/backend проверки до интеграционного финала. Отличай property на известном синтетическом DGP от вывода на admitted real data. В профиле baseline Python 3.14 DoWhy/EconML исключены markers; не выдавай их отсутствие за положительный backend witness и не собирай параллельный shim ради обхода.

`FIT-01` относится к causal TMLE owner в F. Для новых public causal facades проверяй consumer ABI, а не только отсутствие reflection. При unresolved estimand/authority/input issue оставляй finding limited/held. Full production inputs остаются локально; точные data-dependent остатки передавай G для локального run на candidate SHA.

Публикуй законченные slices как `codex/e02-F-<slug>` branch + implementation commit + handoff JSON по общему протоколу. G получает код и receipts через fetch/PR; не предполагай доступность чатов. Не пушь `main`, не форсируй/не переписывай историю.
