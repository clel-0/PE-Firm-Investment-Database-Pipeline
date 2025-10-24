# PE Firm Database Pipeline

Python-based automation to extract PE Firm members of the Australian Investment Council and construct a comprehensive database of their portfolio companies as well as the founders/owners who sold them.

## Installation
Within the terminal enter each of the following commands sequentially
```bash
git clone https://github.com/clel-0/PE-Firm-Investment-Database-Pipeline
cd pipeline
python -m venv venv
source venv/bin/activate   # macOS/Linux
venv\Scripts\activate      # Windows
pip install -r requirements.txt
playwright install
```
Currently, only the seed_aic.py is fully operational and accurate. founded_year.py is not yet being used to add founding years to PE_firms.csv due to the appearance of 429 errors in response to GoogleAPI requests, that still need to be resolved. 

To run seed_aic.py, enter the following within the terminal:

```bash
python seed_aic.py
```

and to execute the test run for founded_year.py enter the following within the terminal:

```bash
python founded_year.py
```

## Description of Methodology

### Phase 1: Australian PE firms identification

Aim:
Seed list: crawl Australian Investment Council members page and parse PE firms

Context:
