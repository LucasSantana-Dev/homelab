{{- define "nextcloud.name" -}}nextcloud{{- end }}
{{- define "nextcloud.fullname" -}}{{ .Release.Name }}-nextcloud{{- end }}
{{- define "nextcloud.mariadb.fullname" -}}{{ .Release.Name }}-mariadb{{- end }}
{{- define "nextcloud.redis.fullname" -}}{{ .Release.Name }}-redis{{- end }}
