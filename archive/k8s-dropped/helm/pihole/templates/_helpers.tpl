{{- define "pihole.name" -}}
{{- .Chart.Name }}
{{- end }}

{{- define "pihole.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
