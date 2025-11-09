# Scan results

{{- define "renderResult" }}
{{- if (or (gt (len .Vulnerabilities) 0) (gt (len .Misconfigurations) 0) (gt (len .Secrets) 0)) }}
## Target: {{ escapeXML .Target }}

**Type:** {{ .Type }}

{{- if gt (len .Vulnerabilities) 0 }}
### Vulnerabilities ({{ len .Vulnerabilities }})

| Package | CVE | Severity | Installed | Fixed |
|---------|-----|----------|-----------|-------|
{{- range .Vulnerabilities }}
| `{{ escapeXML .PkgName }}` | [{{ escapeXML .VulnerabilityID }}](https://nvd.nist.gov/vuln/detail/{{ escapeXML .VulnerabilityID }}) | **{{ escapeXML .Severity }}** | {{ escapeXML .InstalledVersion }} | {{ if .FixedVersion }}{{ escapeXML .FixedVersion }}{{ else }}—{{ end }} |
{{- end }}

{{- end }}

{{- if gt (len .Misconfigurations) 0 }}
### Misconfigurations ({{ len .Misconfigurations }})

| ID | Title | Severity | Message |
|----|-------|----------|---------|
{{- range .Misconfigurations }}
| {{ escapeXML .ID }} | {{ escapeXML .Title }} | {{ escapeXML .Severity }} | {{ escapeXML .Message }}<br>[Details]({{ escapeXML .PrimaryURL }}) |
{{- end }}

{{- end }}

{{- if gt (len .Secrets) 0 }}
### Secrets ({{ len .Secrets }})

| Rule ID | Severity | Category | Match |
|---------|----------|----------|-------|
{{- range .Secrets }}
| `{{ escapeXML .RuleID }}` | **{{ escapeXML .Severity }}** | {{ escapeXML .Category }} | `{{ escapeXML (truncate .Match 100) }}` |
{{- end }}

{{- end }}

{{- else }}
{{- end }}
{{- end }}
{{- if gt (len .) 0 }}
{{- range . }}
{{ template "renderResult" . }}
{{- end }}
{{- else }}
No scan results found.
{{- end }}
