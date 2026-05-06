from pydantic import BaseModel, Field
from typing import List, Optional

class Genre(BaseModel):
    genre_id: int
    name: str

class Keyword(BaseModel):
    keyword_id: int
    name: str

class Language(BaseModel):
    iso_639_1: str
    name: str

class Country(BaseModel):
    iso_3166_1: str
    name: str

class MovieSummary(BaseModel):
    id: int
    title: str
    release_date: Optional[str]
    popularity: Optional[float]
    vote_average: Optional[float]
    vote_count: Optional[int]
    overview: Optional[str]

class MovieDetail(MovieSummary):
    budget: Optional[int]
    revenue: Optional[int]
    runtime: Optional[float]
    original_language: Optional[str]
    status: Optional[str]
    tagline: Optional[str]
    homepage: Optional[str]
    genres: List[str] = []
    keywords: List[str] = []
    spoken_languages: List[str] = []
    cast: List[str] = []
    production_companies: List[str] = []
    production_countries: List[str] = []
