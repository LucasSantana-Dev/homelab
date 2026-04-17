{{- define "vaultwarden.name" -}}
{{- .Chart.Name }}
{{- end }}

{{- define "vaultwarden.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
