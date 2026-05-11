{{- define "wcp.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "wcp.namespace" -}}
{{- if .Values.namespace.nameOverride -}}
{{- .Values.namespace.nameOverride -}}
{{- else -}}
{{- printf "wcp-%s" .Values.global.environment -}}
{{- end -}}
{{- end -}}

{{- define "wcp.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/name: {{ include "wcp.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: wcp
wcp.io/environment: {{ .Values.global.environment }}
{{- end -}}

{{/*
ExternalSecret remoteKey resolver: prepends /wcp/{env}/ unless the item
already supplies an absolute path (starts with '/').
Call: include "wcp.secretRemoteKey" (dict "ctx" $ "key" $item.remoteKey)
*/}}
{{- define "wcp.secretRemoteKey" -}}
{{- $k := .key -}}
{{- if hasPrefix "/" $k -}}
{{- $k -}}
{{- else -}}
{{- printf "/wcp/%s/%s" .ctx.Values.global.environment $k -}}
{{- end -}}
{{- end -}}
