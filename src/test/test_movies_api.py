"""
test_movies_api.py

Pytest suite for the Movies FastAPI application.

Covers:
  Original endpoints
    - GET /movies/search
    - GET /movies/{movie_id}          (found + 404)
    - GET /genres
    - GET /keywords  (with and without ?search=)
    - GET /languages
    - GET /countries

  New Crew & Cast endpoints
    - GET /movies/by-director
    - GET /movies/{movie_id}/cast
    - GET /movies/{movie_id}/crew     (unfiltered + filtered by job)
    - GET /actors/{actor_name}/movies
    - GET /actors/{actor_name}/characters

Known stable data points (TMDB 5000 dataset):
  - Avatar  movie_id = 19995, directed by James Cameron
  - Tom Hanks appears in Forrest Gump (movie_id = 13)
  - Steven Spielberg directed Schindler's List (movie_id = 424)
"""

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

AVATAR_ID = 19995
FORREST_GUMP_ID = 13
SCHINDLERS_LIST_ID = 424


# ===========================================================================
# Original endpoints
# ===========================================================================

class TestSearchMovies:
    def test_returns_list(self, client: TestClient):
        r = client.get("/movies/search")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_filter_by_title(self, client: TestClient):
        r = client.get("/movies/search?title=Avatar")
        assert r.status_code == 200
        titles = [m["title"] for m in r.json()]
        assert any("Avatar" in t for t in titles)

    def test_filter_by_genre(self, client: TestClient):
        r = client.get("/movies/search?genre=Action&limit=5")
        assert r.status_code == 200
        assert len(r.json()) > 0

    def test_filter_by_actor(self, client: TestClient):
        r = client.get("/movies/search?actor=Tom Hanks&limit=10")
        assert r.status_code == 200
        assert len(r.json()) > 0

    def test_filter_by_release_date_range(self, client: TestClient):
        r = client.get("/movies/search?release_date_from=2000-01-01&release_date_to=2000-12-31&limit=10")
        assert r.status_code == 200
        for m in r.json():
            if m["release_date"]:
                assert m["release_date"] >= "2000-01-01"
                assert m["release_date"] <= "2000-12-31"

    def test_sort_by_vote_average_asc(self, client: TestClient):
        r = client.get("/movies/search?sort_by=vote_average&sort_order=asc&limit=5")
        assert r.status_code == 200
        scores = [m["vote_average"] for m in r.json() if m["vote_average"] is not None]
        assert scores == sorted(scores)

    def test_pagination_offset(self, client: TestClient):
        page1 = client.get("/movies/search?limit=5&offset=0").json()
        page2 = client.get("/movies/search?limit=5&offset=5").json()
        ids1 = {m["id"] for m in page1}
        ids2 = {m["id"] for m in page2}
        assert ids1.isdisjoint(ids2), "Pages should not overlap"

    def test_no_results_returns_empty_list(self, client: TestClient):
        r = client.get("/movies/search?title=ZZZNOMATCHZZZ")
        assert r.status_code == 200
        assert r.json() == []

    def test_response_schema(self, client: TestClient):
        r = client.get("/movies/search?limit=1")
        assert r.status_code == 200
        m = r.json()[0]
        for field in ("id", "title"):
            assert field in m


class TestGetMovieDetail:
    def test_known_movie(self, client: TestClient):
        r = client.get(f"/movies/{AVATAR_ID}")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == AVATAR_ID
        assert data["title"] == "Avatar"

    def test_detail_has_enriched_fields(self, client: TestClient):
        r = client.get(f"/movies/{AVATAR_ID}")
        assert r.status_code == 200
        data = r.json()
        for field in ("genres", "keywords", "cast", "spoken_languages",
                      "production_companies", "production_countries"):
            assert field in data
            assert isinstance(data[field], list)

    def test_genres_not_empty_for_avatar(self, client: TestClient):
        r = client.get(f"/movies/{AVATAR_ID}")
        assert r.json()["genres"]

    def test_cast_not_empty_for_avatar(self, client: TestClient):
        r = client.get(f"/movies/{AVATAR_ID}")
        assert r.json()["cast"]

    def test_not_found_returns_404(self, client: TestClient):
        r = client.get("/movies/999999999")
        assert r.status_code == 404


class TestReferenceData:
    def test_genres_returns_list(self, client: TestClient):
        r = client.get("/genres")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "genre_id" in data[0]
        assert "name" in data[0]

    def test_keywords_returns_list(self, client: TestClient):
        r = client.get("/keywords?search=space&limit=5")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        for kw in data:
            assert "space" in kw["name"].lower()

    def test_keywords_no_filter(self, client: TestClient):
        r = client.get("/keywords")
        assert r.status_code == 200
        assert len(r.json()) > 0

    def test_languages_returns_list(self, client: TestClient):
        r = client.get("/languages")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "iso_639_1" in data[0]
        assert "name" in data[0]

    def test_countries_returns_list(self, client: TestClient):
        r = client.get("/countries")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "iso_3166_1" in data[0]
        assert "name" in data[0]


# ===========================================================================
# New Crew & Cast endpoints
# ===========================================================================

class TestMoviesByDirector:
    def test_spielberg_returns_results(self, client: TestClient):
        r = client.get("/movies/by-director?name=Spielberg&limit=10")
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0

    def test_spielberg_includes_schindlers_list(self, client: TestClient):
        r = client.get("/movies/by-director?name=Spielberg&limit=50")
        ids = [m["id"] for m in r.json()]
        assert SCHINDLERS_LIST_ID in ids

    def test_cameron_includes_avatar(self, client: TestClient):
        r = client.get("/movies/by-director?name=Cameron&limit=20")
        ids = [m["id"] for m in r.json()]
        assert AVATAR_ID in ids

    def test_response_schema(self, client: TestClient):
        r = client.get("/movies/by-director?name=Nolan&limit=1")
        assert r.status_code == 200
        m = r.json()[0]
        for field in ("id", "title", "popularity", "vote_average"):
            assert field in m

    def test_unknown_director_returns_empty(self, client: TestClient):
        r = client.get("/movies/by-director?name=ZZZNOMATCHZZZ")
        assert r.status_code == 200
        assert r.json() == []

    def test_missing_name_param_returns_422(self, client: TestClient):
        r = client.get("/movies/by-director")
        assert r.status_code == 422

    def test_sort_by_release_date_desc(self, client: TestClient):
        r = client.get("/movies/by-director?name=Spielberg&sort_by=release_date&sort_order=desc&limit=10")
        assert r.status_code == 200
        dates = [m["release_date"] for m in r.json() if m["release_date"]]
        assert dates == sorted(dates, reverse=True)

    def test_pagination(self, client: TestClient):
        page1 = client.get("/movies/by-director?name=Spielberg&limit=3&offset=0").json()
        page2 = client.get("/movies/by-director?name=Spielberg&limit=3&offset=3").json()
        ids1 = {m["id"] for m in page1}
        ids2 = {m["id"] for m in page2}
        assert ids1.isdisjoint(ids2)


class TestMovieCast:
    def test_avatar_cast_returns_list(self, client: TestClient):
        r = client.get(f"/movies/{AVATAR_ID}/cast")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_avatar_cast_schema(self, client: TestClient):
        r = client.get(f"/movies/{AVATAR_ID}/cast")
        member = r.json()[0]
        for field in ("movie_id", "name", "character", "order"):
            assert field in member

    def test_avatar_cast_ordered_by_billing(self, client: TestClient):
        r = client.get(f"/movies/{AVATAR_ID}/cast")
        orders = [m["order"] for m in r.json() if m["order"] is not None]
        assert orders == sorted(orders)

    def test_avatar_top_billed_actor(self, client: TestClient):
        r = client.get(f"/movies/{AVATAR_ID}/cast")
        top = r.json()[0]
        assert top["name"] == "Sam Worthington"
        assert top["character"] == "Jake Sully"

    def test_unknown_movie_returns_empty(self, client: TestClient):
        r = client.get("/movies/999999999/cast")
        assert r.status_code == 200
        assert r.json() == []

    def test_all_members_belong_to_movie(self, client: TestClient):
        r = client.get(f"/movies/{AVATAR_ID}/cast")
        for m in r.json():
            assert m["movie_id"] == AVATAR_ID


class TestMovieCrew:
    def test_avatar_crew_returns_list(self, client: TestClient):
        r = client.get(f"/movies/{AVATAR_ID}/crew")
        assert r.status_code == 200
        assert len(r.json()) > 0

    def test_avatar_crew_schema(self, client: TestClient):
        r = client.get(f"/movies/{AVATAR_ID}/crew")
        member = r.json()[0]
        for field in ("movie_id", "name", "department", "job"):
            assert field in member

    def test_filter_by_job_director(self, client: TestClient):
        r = client.get(f"/movies/{AVATAR_ID}/crew?job=Director")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["name"] == "James Cameron"
        assert data[0]["job"] == "Director"

    def test_filter_by_department(self, client: TestClient):
        r = client.get(f"/movies/{AVATAR_ID}/crew?department=Directing")
        assert r.status_code == 200
        for m in r.json():
            assert m["department"].lower() == "directing"

    def test_filter_job_case_insensitive(self, client: TestClient):
        r = client.get(f"/movies/{AVATAR_ID}/crew?job=director")
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_unknown_movie_returns_empty(self, client: TestClient):
        r = client.get("/movies/999999999/crew")
        assert r.status_code == 200
        assert r.json() == []

    def test_all_members_belong_to_movie(self, client: TestClient):
        r = client.get(f"/movies/{AVATAR_ID}/crew")
        for m in r.json():
            assert m["movie_id"] == AVATAR_ID


class TestActorMovies:
    def test_tom_hanks_returns_results(self, client: TestClient):
        r = client.get("/actors/Tom%20Hanks/movies")
        assert r.status_code == 200
        assert len(r.json()) > 0

    def test_tom_hanks_includes_forrest_gump(self, client: TestClient):
        r = client.get("/actors/Tom%20Hanks/movies?limit=50")
        ids = [m["id"] for m in r.json()]
        assert FORREST_GUMP_ID in ids

    def test_response_schema(self, client: TestClient):
        r = client.get("/actors/Tom%20Hanks/movies?limit=1")
        m = r.json()[0]
        for field in ("id", "title", "popularity", "vote_average"):
            assert field in m

    def test_partial_name_match(self, client: TestClient):
        r = client.get("/actors/Hanks/movies?limit=10")
        assert r.status_code == 200
        assert len(r.json()) > 0

    def test_unknown_actor_returns_empty(self, client: TestClient):
        r = client.get("/actors/ZZZNOMATCHZZZ/movies")
        assert r.status_code == 200
        assert r.json() == []

    def test_sort_by_vote_average_desc(self, client: TestClient):
        r = client.get("/actors/Tom%20Hanks/movies?sort_by=vote_average&sort_order=desc&limit=10")
        assert r.status_code == 200
        scores = [m["vote_average"] for m in r.json() if m["vote_average"] is not None]
        assert scores == sorted(scores, reverse=True)

    def test_pagination(self, client: TestClient):
        page1 = client.get("/actors/Tom%20Hanks/movies?limit=3&offset=0").json()
        page2 = client.get("/actors/Tom%20Hanks/movies?limit=3&offset=3").json()
        ids1 = {m["id"] for m in page1}
        ids2 = {m["id"] for m in page2}
        assert ids1.isdisjoint(ids2)


class TestActorCharacters:
    def test_tom_hanks_returns_results(self, client: TestClient):
        r = client.get("/actors/Tom%20Hanks/characters")
        assert r.status_code == 200
        assert len(r.json()) > 0

    def test_response_schema(self, client: TestClient):
        r = client.get("/actors/Tom%20Hanks/characters?limit=1")
        c = r.json()[0]
        for field in ("movie_id", "title", "character"):
            assert field in c

    def test_forrest_gump_character_present(self, client: TestClient):
        r = client.get("/actors/Tom%20Hanks/characters?limit=100")
        entries = {(e["movie_id"], e["character"]) for e in r.json()}
        assert (FORREST_GUMP_ID, "Forrest Gump") in entries

    def test_unknown_actor_returns_empty(self, client: TestClient):
        r = client.get("/actors/ZZZNOMATCHZZZ/characters")
        assert r.status_code == 200
        assert r.json() == []

    def test_sort_by_release_date_desc(self, client: TestClient):
        r = client.get("/actors/Tom%20Hanks/characters?sort_by=release_date&sort_order=desc&limit=10")
        assert r.status_code == 200
        dates = [e["release_date"] for e in r.json() if e["release_date"]]
        assert dates == sorted(dates, reverse=True)

    def test_sort_by_release_date_asc(self, client: TestClient):
        r = client.get("/actors/Tom%20Hanks/characters?sort_by=release_date&sort_order=asc&limit=10")
        assert r.status_code == 200
        dates = [e["release_date"] for e in r.json() if e["release_date"]]
        assert dates == sorted(dates)

    def test_pagination(self, client: TestClient):
        page1 = client.get("/actors/Tom%20Hanks/characters?limit=3&offset=0").json()
        page2 = client.get("/actors/Tom%20Hanks/characters?limit=3&offset=3").json()
        ids1 = {(e["movie_id"], e["character"]) for e in page1}
        ids2 = {(e["movie_id"], e["character"]) for e in page2}
        assert ids1.isdisjoint(ids2)

