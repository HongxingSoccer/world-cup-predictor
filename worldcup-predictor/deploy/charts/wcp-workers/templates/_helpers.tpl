{{- define "wcp-workers.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "wcp-workers.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "wcp-workers.commonLabels" -}}
helm.sh/chart: {{ include "wcp-workers.chart" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: wcp
{{- end -}}

{{- define "wcp-workers.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default "wcp-workers" .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{- define "wcp-workers.mlflowServiceAccountName" -}}
{{- if .Values.mlflow.serviceAccount.create -}}
{{- default "wcp-mlflow" .Values.mlflow.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.mlflow.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{/*
Resolve the image reference for a worker. Workers default to the chart-level
image (.Values.image.*) but can override repository / tag / registry per
worker (e.g. card-worker carries Chromium → different image).

Call: include "wcp-workers.workerImage" (dict "global" .Values.image "override" $worker.image)
*/}}
{{- define "wcp-workers.workerImage" -}}
{{- $g := .global -}}
{{- $o := .override -}}
{{- $registry := default $g.registry $o.registry -}}
{{- $repository := default $g.repository $o.repository -}}
{{- $tag := default $g.tag $o.tag | default "latest" -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" $registry $repository $tag -}}
{{- else -}}
{{- printf "%s:%s" $repository $tag -}}
{{- end -}}
{{- end -}}

{{/*
Render image reference for a single-image component (flower, mlflow).
*/}}
{{- define "wcp-workers.componentImage" -}}
{{- $i := . -}}
{{- $tag := $i.tag | default "latest" -}}
{{- if $i.registry -}}
{{- printf "%s/%s:%s" $i.registry $i.repository $tag -}}
{{- else -}}
{{- printf "%s:%s" $i.repository $tag -}}
{{- end -}}
{{- end -}}
