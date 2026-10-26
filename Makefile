PYTHON ?= python

.PHONY: all download clean load analyze maps export test db-up db-down

all: ## Full pipeline from an empty data/ folder
	$(PYTHON) run.py all

download: ## Download ONISR, INSEE and GeoJSON files into data/raw/
	$(PYTHON) run.py download

clean: ## Standardize and clean, write the 3 grains to data/processed/
	$(PYTHON) run.py clean

load: ## Load the star schema into PostgreSQL
	$(PYTHON) run.py load

analyze: ## Statistics, severity model, figures and findings
	$(PYTHON) run.py analyze

maps: ## Interactive HTML maps
	$(PYTHON) run.py maps

export: ## Export the star schema as CSV to data/gold/ for Power BI
	$(PYTHON) run.py export

test: ## Unit tests
	$(PYTHON) run.py test

db-up: ## Start PostgreSQL 16 in Docker
	docker compose up -d --wait

db-down:
	docker compose down
