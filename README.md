# CompanySift - UK Company Website Discovery Tool

A CLI tool that automatically discovers websites for UK companies from registry data. It processes CSV files containing company information (from Companies House), searches for company websites using DuckDuckGo, filters out aggregator sites, and outputs enriched CSV files with discovered URLs and confidence scores.

## Features

- **Batch Processing** - Process thousands of companies with checkpoint/resume capability
- **Intelligent Scoring** - Confidence scores (0-100) based on domain matching, TLD relevance, and search position
- **Aggregator Filtering** - Automatically filters out Companies House, CompanyCheck, and other aggregator sites
- **Rate Limiting** - Built-in rate limiting to respect API limits (4.5 req/sec)
- **Configurable** - YAML-based configuration without code changes
- **Resume Support** - Checkpoint system allows resuming interrupted runs

## Requirements

- Python 3.11+
- DuckDuckGo RapidAPI key (see [Configuration](#configuration))

## Installation

```bash
# Clone the repository
git clone https://github.com/iamthew4lrus789/companysift
cd companysift

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your DUCKDUCKGO_API_KEY
```

## Configuration

### API Key Setup

1. Sign up at [RapidAPI](https://rapidapi.com/)
2. Subscribe to the [DuckDuckGo Web Search API](https://rapidapi.com/Glavier/api/duckduckgo8)
3. Copy your API key from the RapidAPI dashboard
4. Add it to your `.env` file:

```bash
DUCKDUCKGO_API_KEY=your_rapidapi_key_here
```

The API key must be at least 10 characters long.

### Configuration File

Edit `config/config.yaml` to customize behavior:

```yaml
search:
  provider: "duckduckgo"
  api_key: "${DUCKDUCKGO_API_KEY}"  # Uses environment variable
  rate_limit: 4.5                    # Requests per second
  timeout: 30                        # Request timeout in seconds

scoring:
  min_confidence: 65                 # Minimum score to include result
  weights:
    domain_match: 0.5
    tld_relevance: 0.3
    position: 0.2

filtering:
  blocklist:
    - find-and-update.company-information.service.gov.uk
    - companycheck.co.uk
    - endole.co.uk
    # ... more aggregator sites
```

## Usage

### Basic Processing

```bash
# Show help
./company-sift --help

# Process companies from CSV
./company-sift process input.csv -o output.csv

# Resume interrupted processing
./company-sift process input.csv -o output.csv --resume
```

### Input CSV Format

Your input CSV should contain company data with these columns (column names are flexible):

| Column | Description | Example |
|--------|-------------|---------|
| CompanyNumber | Companies House number | 12345678 |
| CompanyName | Company name | Acme Widgets Ltd |
| RegAddress.PostCode | Registered postcode | SW1A 1AA |
| CompanyStatus | Status (Active, Dissolved, etc.) | Active |
| SICCode.SicText_1 | Primary SIC code description | Manufacturing |

See `data/samples/` for example files.

### Output

The tool outputs a CSV with additional columns:

| Column | Description |
|--------|-------------|
| DiscoveredURL | Best matching website URL |
| ConfidenceScore | Score from 0-100 |
| URLSource | How the URL was found |
| SearchTimestamp | When the search was performed |

### Blocklist Management

```bash
# View current blocklist
./company-sift blocklist list

# Add a site to blocklist
./company-sift blocklist add example.com

# Remove from blocklist
./company-sift blocklist remove example.com
```

## Sample Data

### Using Provided Samples

The `data/samples/` directory contains synthetic company data for testing:

```bash
./company-sift process data/samples/companies_sample.csv -o output/results.csv
```

### Getting Real Data

For real UK company data, download from [Companies House](https://download.companieshouse.gov.uk/en_output.html):

1. Visit the Companies House download page
2. Download the "Basic Company Data" CSV
3. The file contains all active UK companies with registration details

## Architecture

```
companysift/
├── src/
│   ├── cli/           # Command-line interface
│   ├── core/          # Configuration, models, exceptions
│   ├── csv_processor/ # CSV reading and writing
│   ├── search/        # DuckDuckGo API client
│   ├── scoring/       # Confidence scoring algorithms
│   ├── filtering/     # Blocklist and domain frequency
│   ├── state/         # Checkpoint/resume system
│   └── utils/         # Logging and utilities
├── tests/             # Unit and integration tests
├── config/            # YAML configuration files
└── data/samples/      # Sample data for testing
```

### Key Components

- **Search Client** (`src/search/client.py`): Handles DuckDuckGo API requests with retry logic
- **Confidence Scorer** (`src/scoring/confidence.py`): Multi-factor scoring using fuzzy matching
- **Blocklist Filter** (`src/filtering/blocklist.py`): Filters aggregator sites with subdomain support
- **Checkpoint Manager** (`src/state/checkpoint.py`): SQLite-based resume capability

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_confidence_scorer.py -v

# Run tests matching pattern
pytest tests/ -k "api_key" -v
```

## Troubleshooting

### API Key Errors

```
ERROR: DuckDuckGo API key is required but not configured.
```
**Solution:** Set `DUCKDUCKGO_API_KEY` in your `.env` file.

```
ERROR: Invalid API key format. API key must be at least 10 characters.
```
**Solution:** Verify your API key is correct and complete.

### Network Errors

```
Network error during search: HTTPSConnectionPool(...)
```
**Solution:** Check your internet connection and verify API key validity on RapidAPI.

### Rate Limiting

```
API request failed with status 429
```
**Solution:** You've exceeded the rate limit. Wait a few seconds or reduce `rate_limit` in config.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [DuckDuckGo](https://duckduckgo.com/) for the search API
- [Companies House](https://www.gov.uk/government/organisations/companies-house) for UK company data
- [RapidAPI](https://rapidapi.com/) for API hosting
