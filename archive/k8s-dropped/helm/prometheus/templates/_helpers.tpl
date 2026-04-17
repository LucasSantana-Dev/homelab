{{- define "prometheus.name" -}}
{{- .Chart.Name }}
{{- end }}

{{- define "prometheus.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name }}
{{- end }}
