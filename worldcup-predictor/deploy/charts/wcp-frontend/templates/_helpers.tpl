{{/*
Standard labels follow the Helm best-practice set
(see https://helm.sh/docs/chart_best_practices/labels/).
*/}}

{{- define "wcp-frontend.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
fullname is the chart name (not prefixed with Release.Name) so the in-cluster
DNS hostnames (`wcp-frontend.<ns>.svc`) stay stable across `helm install --name`
choices. The umbrella's Ingress + cross-service env vars hardcode these names.
*/}}
{{- define "wcp-frontend.fullname" -}}
{{- default .Chart.Name .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "wcp-frontend.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "wcp-frontend.labels" -}}
helm.sh/chart: {{ include "wcp-frontend.chart" . }}
{{ include "wcp-frontend.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: wcp
{{- end -}}

{{- define "wcp-frontend.selectorLabels" -}}
app.kubernetes.io/name: {{ include "wcp-frontend.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "wcp-frontend.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "wcp-frontend.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{/*
Image reference: registry / repository : tag.
Tag falls back to Chart.AppVersion so `helm template` works without
a CD pipeline injecting a SHA.
*/}}
{{- define "wcp-frontend.image" -}}
{{- $tag := .Values.image.tag | default .Chart.AppVersion -}}
{{- if .Values.image.registry -}}
{{- printf "%s/%s:%s" .Values.image.registry .Values.image.repository $tag -}}
{{- else -}}
{{- printf "%s:%s" .Values.image.repository $tag -}}
{{- end -}}
{{- end -}}
