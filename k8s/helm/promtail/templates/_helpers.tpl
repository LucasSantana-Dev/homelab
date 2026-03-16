{{- define "promtail.name" -}}
{{- .Chart.Name }}
{{- end }}

{{- define "promtail.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name }}
{{- end }}
