"""
movies_api.py

FastAPI application for querying the movies DuckDB database.

Endpoints:
  GET /movies/search          - full-text / multi-filter search
  GET /movies/{movie_id}      - get a single movie by ID
  GET /genres                 - list all genres
  GET /keywords               - list all keywords
  GET /languages              - list all spoken languages

Run:
    uvicorn movies_api:app --reload --port 8000
    Swagger UI: http://localhost:8000/docs
"""


from contextlib import asynccontextmanager
from models.movies_models import (Genre,
                                  Keyword,
                                  Language,
                                  Country,
                                  MovieSummary,
                                  MovieDetail)
from ingestion.utils import get_db
import duckdb
from typing import List, Optional
import os
from fastapi import FastAPI, HTTPException, Query, Depends


app = FastAPI(
    title="Movies API",
    description="Query and search movies information stored in DuckDB",
    version="1.0.0",
)


def _enrich_movie(movie_row: dict, con: duckdb.DuckDBPyConnection) -> MovieDetail:
    mid = movie_row["id"]

    def fetch_names(table: str, name_col: str = "name") -> List[str]:
        rows = con.execute(
            f"SELECT {name_col} FROM {table} WHERE movie_id = ? ORDER BY 1", [mid]
        ).fetchall()
        return [r[0] for r in rows if r[0]]

    def fetch_cast_names() -> List[str]:
        rows = con.execute(
            "SELECT name FROM movie_cast WHERE movie_id = ? ORDER BY \"order\"", [mid]
        ).fetchall()
        return [r[0] for r in rows if r[0]]

    return MovieDetail(
        **movie_row,
        genres=fetch_names("movie_genres"),
        keywords=fetch_names("movie_keywords"),
        spoken_languages=fetch_names("movie_spoken_languages"),
        cast=fetch_cast_names(),
        production_companies=fetch_names("movie_production_companies"),
        production_countries=fetch_names("movie_production_countries"),
    )


@app.get(
    "/movies/search",
    response_model=List[MovieSummary],
    summary="Search movies",
    tags=["Movies"],
)
def search_movies(
    # Filter parameters
    genre: Optional[str] = Query(None, description="Filter by genre name (e.g. 'Action')"),
    keyword: Optional[str] = Query(None, description="Filter by keyword (e.g. 'space war')"),
    language: Optional[str] = Query(
        None, description="Filter by spoken language ISO code or name (e.g. 'en' or 'English')"
    ),
    country: Optional[str] = Query(
        None, description="Filter by production country ISO code or name (e.g. 'US' or 'United States')"
    ),
    actor: Optional[str] = Query(None, description="Filter by actor name (partial match)"),
    release_date_from: Optional[str] = Query(
        None, description="Release date range start (YYYY-MM-DD)"
    ),
    release_date_to: Optional[str] = Query(
        None, description="Release date range end (YYYY-MM-DD)"
    ),
    title: Optional[str] = Query(None, description="Partial title search (case-insensitive)"),

    # Pagination / sorting
    sort_by: str = Query(
        "popularity",
        description="Sort field: popularity | vote_average | release_date",
        enum=["popularity", "vote_average", "release_date"],
    ),
    sort_order: str = Query("desc", description="Sort direction", enum=["asc", "desc"]),
    limit: int = Query(20, ge=1, le=100, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    con: duckdb.DuckDBPyConnection = Depends(get_db),
):
    """
    Search movies with optional filters:
    - **genre**: filter by genre name
    - **keyword**: filter by keyword
    - **language**: filter by spoken language (ISO code or name)
    - **country**: filter by production country (ISO code or name)
    - **actor**: filter by actor name (partial match)
    - **release_date_from / release_date_to**: filter by release date range
    - **title**: partial title match
    """
    params = []

    # Base query: join to filter tables only when a filter is active
    joins = ""
    conditions = ["1=1"]

    if genre:
        joins += " JOIN movie_genres mg ON m.id = mg.movie_id"
        conditions.append("LOWER(mg.name) = LOWER(?)")
        params.append(genre)

    if keyword:
        joins += " JOIN movie_keywords mk ON m.id = mk.movie_id"
        conditions.append("LOWER(mk.name) = LOWER(?)")
        params.append(keyword)

    if language:
        joins += " JOIN movie_spoken_languages ml ON m.id = ml.movie_id"
        conditions.append("LOWER(ml.iso_639_1) = LOWER(?) OR LOWER(ml.name) = LOWER(?)")
        params.extend([language, language])

    if country:
        joins += " JOIN movie_production_countries mpc ON m.id = mpc.movie_id"
        conditions.append("LOWER(mpc.iso_3166_1) = LOWER(?) OR LOWER(mpc.name) = LOWER(?)")
        params.extend([country, country])

    if actor:
        joins += " JOIN movie_cast mca ON m.id = mca.movie_id"
        conditions.append("LOWER(mca.name) LIKE LOWER(?)")
        params.append(f"%{actor}%")

    if release_date_from:
        conditions.append("m.release_date >= ?")
        params.append(release_date_from)

    if release_date_to:
        conditions.append("m.release_date <= ?")
        params.append(release_date_to)

    if title:
        conditions.append("LOWER(m.title) LIKE LOWER(?)")
        params.append(f"%{title}%")

    where_clause = " AND ".join(conditions)
    sort_col = {"popularity": "m.popularity", "vote_average": "m.vote_average", "release_date": "m.release_date"}[sort_by]

    sql = f"""SELECT DISTINCT            
                    m.id, m.title, m.release_date, m.popularity,            
                    m.vote_average, m.vote_count, m.overview        
               FROM movies m        {joins}        
               WHERE {where_clause}        
               ORDER BY {sort_col} {sort_order.upper()} 
               NULLS LAST        
               LIMIT ? OFFSET ?    
    """
    params.extend([limit, offset])

    rows = con.execute(sql, params).fetchdf()
    if rows.empty:
        return []

    return [MovieSummary(**row) for row in rows.to_dict(orient="records")]


@app.get(
    "/movies/{movie_id}",
    response_model=MovieDetail,
    summary="Get movie details",
    tags=["Movies"],
)
def get_movie(
    movie_id: int,
    con: duckdb.DuckDBPyConnection = Depends(get_db),
):
    """
    Retrieve full details for a single movie including genres, keywords,
    spoken languages, cast, production companies and countries.
    """
    row = con.execute(
        """
        SELECT id, title, release_date, popularity, vote_average, vote_count,
               overview, budget, revenue, runtime, original_language,
               status, tagline, homepage
        FROM movies WHERE id = ?
        """,
        [movie_id],
    ).fetchdf()

    if row.empty:
        raise HTTPException(status_code=404, detail=f"Movie {movie_id} not found.")

    movie_row = row.to_dict(orient="records")[0]
    return _enrich_movie(movie_row, con)


@app.get(
    "/genres",
    response_model=List[Genre],
    summary="List all genres",
    tags=["Reference Data"],
)
def list_genres(con: duckdb.DuckDBPyConnection = Depends(get_db)):
    """Return all distinct genres available in the database."""
    rows = con.execute(
        """SELECT DISTINCT genre_id, name 
           FROM movie_genres 
           ORDER BY name
        """
    ).fetchall()
    return [Genre(genre_id=r[0], name=r[1]) for r in rows]


@app.get(
    "/keywords",
    response_model=List[Keyword],
    summary="List all keywords",
    tags=["Reference Data"],
)
def list_keywords(
    search: Optional[str] = Query(None, description="Optional partial keyword search"),
    con: duckdb.DuckDBPyConnection = Depends(get_db),
):
    """Return all distinct keywords, with optional partial name search."""
    if search:
        rows = con.execute(
            """SELECT DISTINCT keyword_id, name 
                     FROM movie_keywords 
                     WHERE LOWER(name) 
                     LIKE LOWER(?) 
                     ORDER BY name
                """,
            [f"%{search}%"],
        ).fetchall()
    else:
        rows = con.execute(
            """SELECT DISTINCT keyword_id, name 
               FROM movie_keywords 
               ORDER BY name
            """
        ).fetchall()
    return [Keyword(keyword_id=r[0], name=r[1]) for r in rows]


@app.get(
    "/languages",
    response_model=List[Language],
    summary="List all spoken languages",
    tags=["Reference Data"],
)
def list_languages(con: duckdb.DuckDBPyConnection = Depends(get_db)):
    """Return all distinct spoken languages available in the database."""
    rows = con.execute(
        """SELECT DISTINCT iso_639_1, name 
           FROM movie_spoken_languages 
           ORDER BY name
        """
    ).fetchall()
    return [Language(iso_639_1=r[0], name=r[1]) for r in rows]
