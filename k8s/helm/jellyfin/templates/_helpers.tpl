{{- define "jellyfin.name" -}}
{{- .Chart.Name }}
{{- end }}

{{- define "jellyfin.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name }}
{{- end }}
