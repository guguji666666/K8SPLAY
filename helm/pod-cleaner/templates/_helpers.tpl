# ============================================================
# Helm Helper Templates
# Provides common template functions
# ============================================================

{{/*
# Expand full name
# Format: release-name-chart-name
*/}}
{{- define "pod-cleaner.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
# Generate selector labels
# Used for Deployment selector and Pod template labels
*/}}
{{- define "pod-cleaner.selectorLabels" -}}
app.kubernetes.io/name: {{ include "pod-cleaner.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion }}
app.kubernetes.io/component: cleaner
{{- end }}

{{/*
# Generate common labels
# Used for all resources
*/}}
{{- define "pod-cleaner.labels" -}}
helm.sh/chart: {{ include "pod-cleaner.fullname" . }}
{{ include "pod-cleaner.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
# Get service account name
*/}}
{{- define "pod-cleaner.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "pod-cleaner.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
