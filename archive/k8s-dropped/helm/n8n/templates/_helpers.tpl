{{- define "n8n.name" -}}
{{- .Chart.Name }}
{{- end }}

{{- define "n8n.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
