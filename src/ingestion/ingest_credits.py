"""
ingest_credits_csv.py

Reads a credits CSV file (movie_id, title, cast, crew) and ingests it into
three normalized DuckDB tables:
  - movies_credits  : (movie_id, title)        -- thin reference table
  - movie_cast      : one row per cast member   -- foreign key: movie_id
  - movie_crew      : one row per crew member   -- foreign key: movie_id
"""

from src.ingestion.utils import expand_json_column

import duckdb
import pandas as pd
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger()


def ingest_credits(csv_path: str, db_path: str) -> None:
    logger.info(f"Reading CSV: {csv_path}")
    df = pd.read_csv(
        csv_path,
        dtype={
            "movie_id": "Int64",
            "title":    str,
            "cast":     str,
            "crew":     str,
        },
    )
    logger.info(f"Loaded {len(df):,} rows.")

    df_credits = df[["movie_id", "title"]].copy()

    # Cast table
    # Fields per cast member:
    # cast_id, character, credit_id, gender, id, person_id, name, order
    df_cast = expand_json_column(df, "cast", "movie_id")
    if not df_cast.empty:
        df_cast = df_cast.rename(columns={"id": "person_id"})
        # Ensure consistent column order / types
        cast_cols = ["movie_id", "cast_id", "person_id", "name", "character",
                     "gender", "order", "credit_id"]
        df_cast = df_cast.reindex(columns=cast_cols)
        df_cast["movie_id"] = df_cast["movie_id"].astype("Int64")
        df_cast["cast_id"]  = pd.to_numeric(df_cast["cast_id"],  errors="coerce").astype("Int64")
        df_cast["person_id"]= pd.to_numeric(df_cast["person_id"],errors="coerce").astype("Int64")
        df_cast["gender"]   = pd.to_numeric(df_cast["gender"],   errors="coerce").astype("Int64")
        df_cast["order"]    = pd.to_numeric(df_cast["order"],    errors="coerce").astype("Int64")

    # Crew table
    # Fields per crew member:
    # credit_id, department, gender, id (person_id), job, name
    df_crew = expand_json_column(df, "crew", "movie_id")
    if not df_crew.empty:
        df_crew = df_crew.rename(columns={"id": "person_id"})
        crew_cols = ["movie_id", "person_id", "name", "department", "job",
                     "gender", "credit_id"]
        df_crew = df_crew.reindex(columns=crew_cols)
        df_crew["movie_id"]  = df_crew["movie_id"].astype("Int64")
        df_crew["person_id"] = pd.to_numeric(df_crew["person_id"], errors="coerce").astype("Int64")
        df_crew["gender"]    = pd.to_numeric(df_crew["gender"],    errors="coerce").astype("Int64")


    logger.info(f"Connecting to DuckDB: {db_path}")
    con = duckdb.connect(db_path)

    tables = {
        "movies_credits": df_credits,
        "movie_cast":     df_cast,
        "movie_crew":     df_crew,
    }

    for table_name, data in tables.items():
        con.execute(f"DROP TABLE IF EXISTS {table_name}")
        con.execute(f"CREATE TABLE {table_name} AS SELECT * FROM data")
        count = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        logger.info(f"{table_name}: {count:,} rows ingested.")

    con.close()
    logger.info("Done...")


def main():

    duckdb_path= os.getenv("DUCKDB_PATH", "movies_credits")
    csv_path = os.getenv("CREDITS_CSV_PATH", "credits.csv")

    ingest_credits(csv_path, duckdb_path )


if __name__ == "__main__":
    main()