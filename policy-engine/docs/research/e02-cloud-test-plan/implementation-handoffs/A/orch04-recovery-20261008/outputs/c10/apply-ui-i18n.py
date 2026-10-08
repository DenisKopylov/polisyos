import json
from pathlib import Path
base=Path('/workspace/ORCH04-C10/policy-engine/apps/runtime-dashboard/src/shared/i18n/locales')
labels={
'en': {'title':'Conditional simulation','authority':'Candidate scenario evidence. Publication authority is not established.','refused':'Simulation observation is unavailable for this run.','candidateUnavailable':'Candidate unavailable','notEstablished':'Not established','valueUnavailable':'Simulation value is unavailable.','worldModel':'World model: {ref}','boundaries':'Units: {units}; time: {time}; sampling uncertainty: {sampling}','checkpointTitle':'Recursive computation checkpoint','checkpointBody':'Partial computation. Root outcome remains pending.','frontier':'Pending frontier: {refs}','completed':'Completed child computations: {refs}','rootN9':'Root N9: {status}','checkpointRefused':'Recursive checkpoint is unavailable.'},
'ru': {'title':'Условная симуляция','authority':'Данные сценария кандидата. Право публикации не установлено.','refused':'Наблюдение симуляции недоступно для этого запуска.','candidateUnavailable':'Кандидат недоступен','notEstablished':'Не установлено','valueUnavailable':'Значение симуляции недоступно.','worldModel':'Модель мира: {ref}','boundaries':'Единицы: {units}; время: {time}; неопределённость выборки: {sampling}','checkpointTitle':'Контрольная точка рекурсивного вычисления','checkpointBody':'Частичное вычисление. Итог корня ещё не получен.','frontier':'Ожидающий фронт: {refs}','completed':'Завершённые дочерние вычисления: {refs}','rootN9':'Корневой N9: {status}','checkpointRefused':'Контрольная точка рекурсии недоступна.'},
'uk': {'title':'Умовна симуляція','authority':'Дані сценарію кандидата. Право публікації не встановлено.','refused':'Спостереження симуляції недоступне для цього запуску.','candidateUnavailable':'Кандидат недоступний','notEstablished':'Не встановлено','valueUnavailable':'Значення симуляції недоступне.','worldModel':'Модель світу: {ref}','boundaries':'Одиниці: {units}; час: {time}; невизначеність вибірки: {sampling}','checkpointTitle':'Контрольна точка рекурсивного обчислення','checkpointBody':'Часткове обчислення. Підсумок кореня ще не отримано.','frontier':'Фронт очікування: {refs}','completed':'Завершені дочірні обчислення: {refs}','rootN9':'Кореневий N9: {status}','checkpointRefused':'Контрольна точка рекурсії недоступна.'}}
for code, values in labels.items():
 p=base/(code+'.json'); s=p.read_text(); old=json.loads(s)['pages']['runs']['overview']
 anchor='\n      "overview": '+json.dumps(old,ensure_ascii=False)+','
 assert s.count(anchor)==1
 nested=json.dumps({'candidateSimulation':values},ensure_ascii=False,indent=2).splitlines()[1:-1]
 block='\n'.join('      '+line[2:] for line in nested)
 s=s.replace(anchor,anchor+'\n'+block+',',1)
 json.loads(s);p.write_text(s)
p=Path('/workspace/ORCH04-C10/policy-engine/apps/runtime-dashboard/src/features/runs/routes/tabs/OverviewTab.tsx')
s=p.read_text().replace('function CandidateSimulationPanel({ run }: { run: unknown }) {','function CandidateSimulationPanel({ run }: { run: unknown }) {\n  const { t } = useI18n();')
replacements={
'<h4>Conditional simulation</h4>':'<h4>{t("pages.runs.candidateSimulation.title")}</h4>',
'Candidate scenario evidence. Publication authority is not established.':'{t("pages.runs.candidateSimulation.authority")}',
'Simulation observation is unavailable for this run.':'{t("pages.runs.candidateSimulation.refused")}',
': "Candidate unavailable"':': t("pages.runs.candidateSimulation.candidateUnavailable")',
': "not_established"':': t("pages.runs.candidateSimulation.notEstablished")',
': "Simulation value is unavailable."':': t("pages.runs.candidateSimulation.valueUnavailable")',
'World model: {row.world_model_record_content_hash}':'{t("pages.runs.candidateSimulation.worldModel", { ref: row.world_model_record_content_hash })}',
'{`Units: ${String(evidence.unit_binding_status ?? "not_established")}; time: ${String(evidence.time_binding_status ?? "not_established")}; sampling uncertainty: ${String(evidence.sampling_uncertainty_status ?? "not_established")}`}':'{t("pages.runs.candidateSimulation.boundaries", { units: String(evidence.unit_binding_status ?? t("pages.runs.candidateSimulation.notEstablished")), time: String(evidence.time_binding_status ?? t("pages.runs.candidateSimulation.notEstablished")), sampling: String(evidence.sampling_uncertainty_status ?? t("pages.runs.candidateSimulation.notEstablished")) })}',
'<h5>Recursive computation checkpoint</h5>':'<h5>{t("pages.runs.candidateSimulation.checkpointTitle")}</h5>',
'<p>Partial computation. Root outcome remains pending.</p>':'<p>{t("pages.runs.candidateSimulation.checkpointBody")}</p>',
'Pending frontier: {textList(checkpoint.pending_frontier).join(", ")}':'{t("pages.runs.candidateSimulation.frontier", { refs: textList(checkpoint.pending_frontier).join(", ") })}',
'Completed child computations:{" "}\n            {textList(checkpoint.completed_design_refs).join(", ")}':'{t("pages.runs.candidateSimulation.completed", { refs: textList(checkpoint.completed_design_refs).join(", ") })}',
'Root N9: {String(checkpoint.root_n9_status ?? "not_established")}':'{t("pages.runs.candidateSimulation.rootN9", { status: String(checkpoint.root_n9_status ?? t("pages.runs.candidateSimulation.notEstablished")) })}',
'Recursive checkpoint is unavailable.':'{t("pages.runs.candidateSimulation.checkpointRefused")}'
}
for old,new in replacements.items():
 assert old in s,old
 s=s.replace(old,new)
p.write_text(s)
