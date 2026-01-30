# Sample Data

This directory contains synthetic sample data for testing CompanySift.

## Files

### companies_sample.csv

A CSV file with 10 fictional UK companies for testing the tool. These are **not real companies** - the company numbers and details are fabricated for demonstration purposes.

**Usage:**
```bash
./company-sift process data/samples/companies_sample.csv -o output/results.csv
```

## Getting Real UK Company Data

For actual company data, download from Companies House:

### Option 1: Basic Company Data (Recommended)

1. Visit: https://download.companieshouse.gov.uk/en_output.html
2. Download "BasicCompanyDataAsOneFile" (CSV format, ~500MB compressed)
3. Extract and use directly with CompanySift

This file contains:
- Company number, name, and registered address
- Company status (Active, Dissolved, etc.)
- SIC codes (industry classification)
- Incorporation date
- Account filing dates

### Option 2: Companies House API

For more targeted data, use the Companies House API:
- https://developer.company-information.service.gov.uk/

You'll need to register for an API key.

## CSV Column Reference

| Column | Description | Example |
|--------|-------------|---------|
| CompanyNumber | 8-digit Companies House number | 12345678 |
| CompanyName | Registered company name | Acme Ltd |
| Postcode | Registered office postcode | SW1A 1AA |
| CompanyStatus | Current status | Active |
| CompanyCategory | Type of company | Private Limited Company |
| PrimarySicCode | 5-digit SIC code | 62020 |
| PrimarySicDescription | SIC code description | IT consultancy |

The tool is flexible with column names - see `src/csv_processor/reader.py` for mapping logic.
