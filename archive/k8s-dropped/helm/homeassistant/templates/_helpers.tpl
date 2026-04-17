{{- define "homeassistant.name" -}}
{{- .Chart.Name }}
{{- end }}

{{- define "homeassistant.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name }}
{{- end }}
