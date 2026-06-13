"""Unit tests for build_prospect_json.py pure layer (issue 049 builder).

Network fetch (fetch_mlb_players) is not exercised — only the pure name
normalization / parse / resolve / merge functions, which carry the correctness
risk (id resolution + best-rank dedup).
"""

from build_prospect_json import (
    build_age_index,
    build_name_index,
    drop_aged_out,
    merge_best_rank,
    normalize_name,
    parse_raw_source,
    resolve,
)


class TestNormalizeName:
    def test_accent_fold_and_lower(self):
        assert normalize_name("José Ramírez") == "jose ramirez"

    def test_strips_suffix_and_period(self):
        assert normalize_name("Jazz Chisholm Jr.") == "jazz chisholm"
        assert normalize_name("Ronald Acuña Jr") == "ronald acuna"

    def test_strips_internal_punctuation(self):
        assert normalize_name("D'Angelo  Ortiz") == "d angelo ortiz"

    def test_empty(self):
        assert normalize_name("") == ""
        assert normalize_name(None) == ""


class TestParseRawSource:
    def test_tab_rows(self):
        text = "2023\t2\tJordan Walker\n2024\t55\tSample Guy\n"
        assert parse_raw_source(text) == [
            (2023, 2, "Jordan Walker"),
            (2024, 55, "Sample Guy"),
        ]

    def test_skips_comments_and_blanks(self):
        text = "# header comment\n\n2025\t1\tName One\n"
        assert parse_raw_source(text) == [(2025, 1, "Name One")]

    def test_skips_malformed_rows(self):
        text = "2023\tNaN\tBad Rank\nonlyonecol\n2024\t3\tGood Row\n"
        assert parse_raw_source(text) == [(2024, 3, "Good Row")]

    def test_comma_fallback_separator(self):
        # tolerate a comma-pasted row when no tabs present
        assert parse_raw_source("2026, 7, Comma Name") == [(2026, 7, "Comma Name")]


class TestResolve:
    def _index(self):
        return build_name_index(
            [
                {"id": 669357, "fullName": "Jordan Walker"},
                {"id": 111, "fullName": "Dup Name"},
                {"id": 222, "fullName": "Dup Name"},  # same-name collision
            ]
        )

    def test_unique_match_resolved(self):
        resolved, review = resolve([(2023, 2, "Jordan Walker")], self._index())
        assert resolved == [
            {"mlb_id": 669357, "best_rank": 2, "year": 2023, "name": "Jordan Walker"}
        ]
        assert review == []

    def test_no_match_goes_to_review(self):
        resolved, review = resolve([(2024, 9, "Undebuted Kid")], self._index())
        assert resolved == []
        assert review[0]["match_count"] == 0
        assert "unmatched" in review[0]["reason"]

    def test_collision_goes_to_review_not_guessed(self):
        resolved, review = resolve([(2025, 4, "Dup Name")], self._index())
        assert resolved == []
        assert review[0]["match_count"] == 2
        assert "collision" in review[0]["reason"]


class TestMergeBestRank:
    def test_keeps_lowest_rank_and_its_year(self):
        resolved = [
            {"mlb_id": 1, "best_rank": 40, "year": 2022, "name": "A"},
            {"mlb_id": 1, "best_rank": 12, "year": 2023, "name": "A"},  # better
            {"mlb_id": 1, "best_rank": 30, "year": 2024, "name": "A"},
        ]
        out = merge_best_rank(resolved)
        assert out[1] == {"best_rank": 12, "best_rank_year": 2023, "name": "A"}

    def test_multiple_ids_independent(self):
        resolved = [
            {"mlb_id": 1, "best_rank": 5, "year": 2023, "name": "A"},
            {"mlb_id": 2, "best_rank": 8, "year": 2023, "name": "B"},
        ]
        out = merge_best_rank(resolved)
        assert set(out) == {1, 2}
        assert out[2]["best_rank"] == 8


class TestDropAgedOut:
    def _players(self):
        return [
            {"id": 527038, "fullName": "Wilmer Flores", "currentAge": 34},  # vet
            {"id": 691023, "fullName": "Jordan Walker", "currentAge": 24},  # prospect
            {"id": 999, "fullName": "No Age Guy"},  # missing currentAge
        ]

    def test_drops_veteran_keeps_prospect(self):
        prospects = {
            527038: {"best_rank": 80, "best_rank_year": 2023, "name": "Wilmer Flores"},
            691023: {"best_rank": 4, "best_rank_year": 2023, "name": "Jordan Walker"},
        }
        age_index = build_age_index(self._players())
        kept, dropped = drop_aged_out(prospects, age_index)
        assert set(kept) == {691023}
        assert dropped[0]["mlb_id"] == 527038
        assert dropped[0]["age"] == 34

    def test_unknown_age_is_kept(self):
        prospects = {999: {"best_rank": 50, "best_rank_year": 2024, "name": "No Age Guy"}}
        age_index = build_age_index(self._players())
        kept, dropped = drop_aged_out(prospects, age_index)
        assert set(kept) == {999}
        assert dropped == []

    def test_custom_max_age(self):
        prospects = {691023: {"best_rank": 4, "best_rank_year": 2023, "name": "Jordan Walker"}}
        age_index = build_age_index(self._players())
        kept, dropped = drop_aged_out(prospects, age_index, max_age=20)
        assert kept == {}
        assert dropped[0]["age"] == 24


class TestBuildAgeIndex:
    def test_maps_id_to_age_skips_missing(self):
        idx = build_age_index(
            [
                {"id": 1, "fullName": "A", "currentAge": 22},
                {"id": 2, "fullName": "B"},  # no age
                {"fullName": "C", "currentAge": 30},  # no id
            ]
        )
        assert idx == {1: 22}
