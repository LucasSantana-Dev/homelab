{{- define "paperless.name" -}}paperless{{- end }}
{{- define "paperless.fullname" -}}{{ .Release.Name }}-paperless{{- end }}
{{- define "paperless.postgresql.fullname" -}}{{ .Release.Name }}-postgresql{{- end }}
{{- define "paperless.redis.fullname" -}}{{ .Release.Name }}-redis{{- end }}
