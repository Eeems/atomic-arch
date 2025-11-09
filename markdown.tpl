{{- define "renderResult" -}}
    {{- if or (gt (len .Vulnerabilities) 0) (gt (len .Misconfigurations) 0) (gt (len .Secrets) 0) -}}
        ## /{{ escapeXML .Target }} ({{ .Type }})
        {{- "\n" -}}
        {{- if gt (len .Vulnerabilities) 0 }}
            {{- "\n" -}}
            {{- ""}}### Vulnerabilities ({{ len .Vulnerabilities }}) {{- "\n" }}
            {{- "\n" -}}
            {{- ""}}| Package | CVE | Severity | Installed | Fixed | {{- "\n" }}
            {{- ""}}|---------|-----|----------|-----------|-------| {{- "\n" }}
            {{- range .Vulnerabilities -}}
                {{- ""}}| `{{ escapeXML .PkgName }}`
                {{- ""}}| [{{ escapeXML .VulnerabilityID }}](https://nvd.nist.gov/vuln/detail/{{ escapeXML .VulnerabilityID }})
                {{- ""}}| **{{ escapeXML .Severity }}**
                {{- ""}}| {{ escapeXML .InstalledVersion }}
                {{- ""}}| {{ if .FixedVersion -}}
                    {{ escapeXML .FixedVersion }}
                {{- else -}}{{/* else .FixedVersion */}}
                    —
                {{- end }}{{/* if .FixedVersion */}}
                {{- ""}}|
                {{- "\n" -}}
            {{- end -}}{{/* range .Vulnerabilities  */}}
            {{- "\n" -}}
        {{- end -}}{{/* if .Vulerabilities */}}
        {{- if gt (len .Misconfigurations) 0}}
            {{- "\n" -}}
            {{- ""}}### Misconfigurations ({{ len .Misconfigurations }}) {{- "\n" }}
            {{- "\n" -}}
            {{- ""}}| ID | Title | Severity | Message | {{- "\n" }}
            {{- ""}}|----|-------|----------|---------| {{- "\n" }}
            {{- range .Misconfigurations -}}
                {{- ""}}| {{ escapeXML .ID }}
                {{- ""}}| {{ escapeXML .Title }}
                {{- ""}}| {{ escapeXML .Severity }}
                {{- ""}}| {{ escapeXML (printf "%.200s" .Message) }}<br>[Details]({{ escapeXML .PrimaryURL }})
                {{- ""}}|
                {{- "\n" -}}
            {{- end}}{{/* range .Misconfigurations */}}
            {{- "\n" -}}
        {{- end -}}{{/* if .Misconfigurations */}}
        {{- if gt (len .Secrets) 0}}
            {{- "\n" -}}
            {{- ""}}### Secrets ({{ len .Secrets }}) {{- "\n" }}
            {{- "\n" -}}
            {{- ""}}| Rule ID | Severity | Category | Match | {{- "\n" }}
            {{- ""}}|---------|----------|----------|-------| {{- "\n" }}
            {{range .Secrets }}
                {{- ""}}| `{{ escapeXML .RuleID }}`
                {{- ""}}| **{{ escapeXML .Severity }}**
                {{- ""}}| {{ escapeXML .Category }}
                {{- ""}}| `{{ escapeXML (printf "%.100s" .Match) }}`
                {{- ""}}|
                {{- "\n" -}}
            {{- end -}}{{/* range .Secrets */}}
            {{- "\n" -}}
        {{- end -}}{{/* if .Secrets */}}
    {{- end -}}{{/* if Any */}}
{{- end -}}{{/* define */}}
{{- ""}}{{/* Main display loop */}}{{"" -}}
{{- if gt (len .) 0 -}}
    # Scan Summary {{- "\n" }}
    {{- "\n" -}}
    {{- range . -}}
        {{- template "renderResult" . -}}
    {{- end -}}
{{- end -}}
