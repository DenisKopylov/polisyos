{{- define "polisyos-cell.namespaceName" -}}
{{- $cellId := required "cell.id is required" .Values.cell.id -}}
{{- printf "polisyos-cell-%s" (trunc 8 $cellId) -}}
{{- end }}

{{- define "polisyos-cell.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride -}}
{{- else -}}
{{- printf "polisyos-cell-%s" (trunc 8 .Values.cell.id) -}}
{{- end -}}
{{- end }}

{{- define "polisyos-cell.labels" -}}
app.kubernetes.io/name: polisyos-cell
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
polisyos.io/cell-id: {{ .Values.cell.id | quote }}
polisyos.io/cell-tier: {{ .Values.cell.tier | quote }}
polisyos.io/region: {{ .Values.cell.region | quote }}
{{- end }}
