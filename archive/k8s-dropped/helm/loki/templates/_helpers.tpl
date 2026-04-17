{{- define "loki.name" -}}
{{- .Chart.Name }}
{{- end }}

{{- define "loki.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name }}
{{- end }}
