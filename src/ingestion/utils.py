import pandas as pd
import json


def _safe_parse_json(value) -> list:
    """Return a Python list from a JSON string, or [] on failure."""
    if pd.isna(value) or not str(value).strip():
        return []
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []

@staticmethod
def expand_json_column(df: pd.DataFrame, json_col: str, movie_id_col: str = "id") -> pd.DataFrame:
    """
    Explode a JSON-array column into one row per element,
    retaining movie_id as a foreign key.
    """
    records = []
    for _, row in df.iterrows():
        movie_id = row[movie_id_col]
        for item in _safe_parse_json(row[json_col]):
            item["movie_id"] = movie_id
            records.append(item)
    return pd.DataFrame(records) if records else pd.DataFrame()


@staticmethod
def build_genres(df: pd.DataFrame) -> pd.DataFrame:
    """movie_id | genre_id | name"""
    out = expand_json_column(df, "genres")
    if out.empty:
        return out
    return out.rename(columns={"id": "genre_id"})[["movie_id", "genre_id", "name"]]

@staticmethod
def build_keywords(df: pd.DataFrame) -> pd.DataFrame:
    """movie_id | keyword_id | name"""
    out = expand_json_column(df, "keywords")
    if out.empty:
        return out
    return out.rename(columns={"id": "keyword_id"})[["movie_id", "keyword_id", "name"]]

@staticmethod
def build_production_companies(df: pd.DataFrame) -> pd.DataFrame:
    """movie_id | company_id | name"""
    out = expand_json_column(df, "production_companies")
    if out.empty:
        return out
    return out.rename(columns={"id": "company_id"})[["movie_id", "company_id", "name"]]

@staticmethod
def build_production_countries(df: pd.DataFrame) -> pd.DataFrame:
    """movie_id | iso_3166_1 | name"""
    out = expand_json_column(df, "production_countries")
    if out.empty:
        return out
    return out[["movie_id", "iso_3166_1", "name"]]

@staticmethod
def build_spoken_languages(df: pd.DataFrame) -> pd.DataFrame:
    """movie_id | iso_639_1 | name"""
    out = expand_json_column(df, "spoken_languages")
    if out.empty:
        return out
    return out[["movie_id", "iso_639_1", "name"]]