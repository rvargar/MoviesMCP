"""
ingest_movies_csv.py

Loads a movies CSV file into DuckDB. JSON array columns are decomposed into
dedicated tables using movie_id as the foreign key.

Tables created:
  - movies                 : core movie data (scalar fields only)
  - movie_genres           : (movie_id, genre_id, name)
  - movie_keywords         : (movie_id, keyword_id, name)
  - movie_production_companies : (movie_id, company_id, name)
  - movie_production_countries : (movie_id, iso_3166_1, name)
  - movie_spoken_languages     : (movie_id, iso_639_1, name)
"""

from src.ingestion.utils import (build_genres,
                                 build_keywords,
                                 build_production_companies,
                                 build_production_countries,
                                 build_spoken_languages)

import os
import duckdb
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger()

JSON_COLUMNS = [
    "genres",
    "keywords",
    "production_companies",
    "production_countries",
    "spoken_languages",
]

def ingest_movies(csv_path: str, db_path: str) -> None:
    logger.info(f"Reading CSV: {csv_path}")
    df = pd.read_csv(
        csv_path,
        dtype={
            "genres":                str,
            "keywords":              str,
            "production_companies":  str,
            "production_countries":  str,
            "spoken_languages":      str,
            "budget":                "Int64",
            "id":                    "Int64",
            "revenue":               "Int64",
            "runtime":               "Float64",
            "vote_average":          "Float64",
            "vote_count":            "Int64",
            "popularity":            "Float64",
            "original_language":     str,
            "original_title":        str,
            "overview":              str,
            "homepage":              str,
            "status":                str,
            "tagline":               str,
            "title":                 str,
            "release_date":          str,
        },
    )
    logger.info(f"Loaded {len(df):,} rows from CSV.")

    # Main table, referenced in CREATE SQL
    df_movies = df.drop(columns=JSON_COLUMNS)


    decomposed = {
        "movie_genres":               build_genres(df),
        "movie_keywords":             build_keywords(df),
        "movie_production_companies": build_production_companies(df),
        "movie_production_countries": build_production_countries(df),
        "movie_spoken_languages":     build_spoken_languages(df),
    }

    logger.info(f"Connecting to DuckDB: {db_path}")
    con = duckdb.connect(db_path)

    con.execute("DROP TABLE IF EXISTS movies")
    con.execute("CREATE TABLE movies AS SELECT * FROM df_movies")
    count = con.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
    logger.info(f"movies: {count:,} rows")

    # Decomposed tables
    for table_name, data in decomposed.items():
        con.execute(f"DROP TABLE IF EXISTS {table_name}")
        if data.empty:
            logger.info(f"{table_name}: no data, skipped.")
            continue
        con.execute(f"CREATE TABLE {table_name} AS SELECT * FROM data")
        count = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        logger.info(f"{table_name}: {count:,} rows")

    con.close()
    logger.info("Done...")


def main():

    duckdb_path= os.getenv("DUCKDB_PATH", "movies.duckdb")
    csv_path = os.getenv("MOVIES_CSV_PATH", "movies.csv")


    ingest_movies(csv_path, duckdb_path)


if __name__ == "__main__":
    main()