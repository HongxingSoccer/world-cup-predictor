{{/*
Render the spec.template.spec body shared by every Celery worker Deployment.
Call: include "wcp-workers.podSpec" (dict "ctx" $ "w" $worker)
  ctx — the root chart context (.)
  w   — the worker config tree (.Values.workers.<name>)
*/}}
{{- define "wcp-workers.podSpec" -}}
{{- $ctx := .ctx -}}
{{- $w := .w -}}
serviceAccountName: {{ include "wcp-workers.serviceAccountName" $ctx }}
{{- with $ctx.Values.imagePullSecrets }}
imagePullSecrets:
  {{- toYaml . | nindent 2 }}
{{- end }}
securityContext:
  {{- toYaml $ctx.Values.podSecurityContext | nindent 2 }}
{{- if and $ctx.Values.topologySpread.enabled (gt (int (default 1 $w.replicaCount)) 1) }}
topologySpreadConstraints:
  - maxSkew: {{ $ctx.Values.topologySpread.maxSkew }}
    topologyKey: {{ $ctx.Values.topologySpread.topologyKey }}
    whenUnsatisfiable: {{ $ctx.Values.topologySpread.whenUnsatisfiable }}
    labelSelector:
      matchLabels:
        app.kubernetes.io/name: {{ $w.name }}
        app.kubernetes.io/instance: {{ $ctx.Release.Name }}
{{- end }}
containers:
  - name: worker
    image: {{ include "wcp-workers.workerImage" (dict "global" $ctx.Values.image "override" (default (dict) $w.image)) | quote }}
    imagePullPolicy: {{ default $ctx.Values.image.pullPolicy ($w.image).pullPolicy }}
    securityContext:
      {{- toYaml $ctx.Values.containerSecurityContext | nindent 6 }}
    {{- with $w.command }}
    command:
      {{- toYaml . | nindent 6 }}
    {{- end }}
    {{- with $w.args }}
    args:
      {{- toYaml . | nindent 6 }}
    {{- end }}
    ports:
      - name: health
        containerPort: {{ $ctx.Values.workerProbes.port }}
        protocol: TCP
    envFrom:
      - configMapRef:
          name: {{ $ctx.Values.envFrom.configMapName }}
          optional: true
      - secretRef:
          name: {{ $ctx.Values.envFrom.secretName }}
          optional: true
    env:
      {{- range $k, $v := $ctx.Values.env }}
      - name: {{ $k }}
        value: {{ $v | quote }}
      {{- end }}
    livenessProbe:
      httpGet:
        path: {{ $ctx.Values.workerProbes.liveness.path }}
        port: health
      initialDelaySeconds: {{ $ctx.Values.workerProbes.liveness.initialDelaySeconds }}
      periodSeconds: {{ $ctx.Values.workerProbes.liveness.periodSeconds }}
      timeoutSeconds: {{ $ctx.Values.workerProbes.liveness.timeoutSeconds }}
      failureThreshold: {{ $ctx.Values.workerProbes.liveness.failureThreshold }}
    readinessProbe:
      httpGet:
        path: {{ $ctx.Values.workerProbes.readiness.path }}
        port: health
      initialDelaySeconds: {{ $ctx.Values.workerProbes.readiness.initialDelaySeconds }}
      periodSeconds: {{ $ctx.Values.workerProbes.readiness.periodSeconds }}
      timeoutSeconds: {{ $ctx.Values.workerProbes.readiness.timeoutSeconds }}
      failureThreshold: {{ $ctx.Values.workerProbes.readiness.failureThreshold }}
    resources:
      {{- toYaml $w.resources | nindent 6 }}
{{- with $ctx.Values.nodeSelector }}
nodeSelector:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- with $ctx.Values.affinity }}
affinity:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- with $ctx.Values.tolerations }}
tolerations:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end -}}


{{/*
Render a ScaledObject for one worker.
Call: include "wcp-workers.scaledObject" (dict "ctx" $ "w" $worker)
*/}}
{{- define "wcp-workers.scaledObject" -}}
{{- $ctx := .ctx -}}
{{- $w := .w -}}
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: {{ $w.name }}
  labels:
    app.kubernetes.io/name: {{ $w.name }}
    app.kubernetes.io/instance: {{ $ctx.Release.Name }}
    {{- include "wcp-workers.commonLabels" $ctx | nindent 4 }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ $w.name }}
  minReplicaCount: {{ $w.keda.minReplicaCount }}
  maxReplicaCount: {{ $w.keda.maxReplicaCount }}
  pollingInterval: {{ $w.keda.pollingInterval }}
  cooldownPeriod: {{ $w.keda.cooldownPeriod }}
  triggers:
    - type: redis
      metadata:
        listName: {{ $w.keda.queue | quote }}
        listLength: {{ $w.keda.listLength | quote }}
        addressFromEnv: REDIS_URL
      authenticationRef:
        name: {{ printf "%s-redis-auth" (include "wcp-workers.name" $ctx) }}
{{- end -}}
