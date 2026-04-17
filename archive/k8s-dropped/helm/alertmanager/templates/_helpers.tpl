{{- define "alertmanager.name" -}}
{{- .Chart.Name }}
{{- end }}

{{- define "alertmanager.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name }}
{{- end }}
