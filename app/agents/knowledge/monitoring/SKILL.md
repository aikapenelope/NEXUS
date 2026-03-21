---
name: monitoring
description: Web monitoring methodology for detecting and reporting changes
version: 1.0.0
tags:
  - monitoring
  - web-scraping
  - change-detection
  - alerts
---

# Web Monitoring Skill

You are monitoring web pages for changes. Follow this methodology to produce
reliable, actionable change reports.

## Monitoring Process

### Step 1: Fetch and Extract
- Navigate to the target URL
- Extract the meaningful content (ignore navigation, ads, footers)
- Record the timestamp of the check

### Step 2: Normalize
- Strip whitespace variations
- Normalize dates to ISO format
- Extract structured data (prices, versions, counts) as key-value pairs

### Step 3: Compare
- Compare current state with your memory of the previous state
- Categorize changes: Added, Removed, Modified
- Assess significance: Critical, Notable, Minor, Noise

### Step 4: Report
- Lead with the most significant change
- Include before/after for modified items
- Provide a significance assessment
- Store the current state in memory for next comparison

## Change Significance Levels

| Level | Definition | Example |
|-------|-----------|---------|
| Critical | Requires immediate attention | Price increase >20%, service outage |
| Notable | Worth knowing about | New feature announced, team change |
| Minor | Informational only | Typo fix, minor UI change |
| Noise | Ignore | Timestamp updates, ad rotation |

## Data Extraction Patterns

### Prices
- Extract: amount, currency, billing period
- Store as: `{"price": 29.99, "currency": "USD", "period": "monthly"}`
- Flag: any change >5% from previous

### Versions
- Extract: version number, release date
- Store as: `{"version": "2.1.0", "date": "2026-03-15"}`
- Flag: major version changes

### Status Pages
- Extract: overall status, per-service status
- Store as: `{"overall": "operational", "services": {"api": "up", "web": "up"}}`
- Flag: any non-operational status

## Memory Format

After each check, update your memory with:
```
[target-name] Last checked: YYYY-MM-DD HH:MM UTC
Key data: {structured data from extraction}
Status: [no-change | changed | new-baseline]
```

This allows you to detect changes on subsequent runs.
