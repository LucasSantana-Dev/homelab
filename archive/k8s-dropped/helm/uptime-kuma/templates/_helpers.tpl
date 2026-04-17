{{- define "uptime-kuma.name" -}}
{{- .Chart.Name }}
{{- end }}

{{- define "uptime-kuma.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
