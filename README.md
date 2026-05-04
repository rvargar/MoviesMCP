# MoviesMCP
Demo repo for Movies DB interaction using MCP server


### install dependencies
```bash
pip install -r requirements.txt
```
You can create uv environment based on requirements.txt file and install dependencies in it.

```bash
uv add -r requirements.txt
uv sync
```

## Database tables - entitites
![image](./misc/ER_movies.png)
Data ingestion script are available in `src/ingestion` folder. It can be used to populate onto in-memory, local SQL DuckDB database.
scripts are separately inggests Credits and Movies data. You need to run both scripts to populate the database with movies and credits data.

```bash
 uv run python src/ingestion/ingest_movies.py
 uv run python src/ingestion/ingest_credits.py
```

## Environment variables
you can create `.env` file in the root directory and add below environment variables to it. These variables are used to configure the database connection and other settings.
See: example_env file for reference.
