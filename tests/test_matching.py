"""Tests for fuzzy company name matching."""

from coeus.matching import normalize, name_similarity, is_match, best_match


class TestNormalize:
    def test_strips_corporate_suffixes(self):
        assert normalize("Apple Inc.") == "apple"

    def test_strips_punctuation(self):
        result = normalize("Johnson & Johnson")
        assert "johnson" in result
        assert "&" not in result

    def test_strips_multiple_noise_words(self):
        assert "foo" in normalize("The International Association of Foo")

    def test_preserves_significant_words(self):
        result = normalize("Red Hat Enterprise")
        assert "red" in result
        assert "hat" in result
        assert "enterprise" in result

    def test_lowercase(self):
        assert normalize("APPLE") == "apple"

    def test_empty_string(self):
        assert normalize("") == ""

    def test_only_noise_words(self):
        # All words are noise — should return empty
        assert normalize("The Inc.") == ""


class TestNameSimilarity:
    def test_identical(self):
        assert name_similarity("Apple", "Apple") == 1.0

    def test_with_corporate_suffix(self):
        assert name_similarity("Apple", "Apple Inc.") == 1.0

    def test_completely_different(self):
        assert name_similarity("Apple", "Microsoft") == 0.0

    def test_partial_overlap(self):
        # {"red","hat"} vs {"red","hat","enterprise"} = 2/3
        sim = name_similarity("Red Hat", "Red Hat Enterprise")
        assert 0.6 < sim < 0.7

    def test_empty_first(self):
        assert name_similarity("", "Apple") == 0.0

    def test_empty_second(self):
        assert name_similarity("Apple", "") == 0.0

    def test_both_empty(self):
        assert name_similarity("", "") == 0.0


class TestIsMatch:
    def test_above_threshold(self):
        assert is_match("Apple", "Apple Inc.", threshold=0.4) is True

    def test_below_threshold_but_substring(self):
        # "red hat" tokens all appear in candidate
        assert is_match("Red Hat", "Red Hat Enterprise Linux Foundation",
                         threshold=0.9) is True

    def test_no_match(self):
        assert is_match("Apple", "Microsoft Corporation", threshold=0.4) is False

    def test_exact_match(self):
        assert is_match("Google", "Google LLC") is True


class TestBestMatch:
    def test_finds_closest(self):
        candidates = [
            {"name": "Microsoft Corp"},
            {"name": "Apple Inc"},
            {"name": "Google LLC"},
        ]
        result = best_match("Apple", candidates)
        assert result["name"] == "Apple Inc"

    def test_respects_threshold(self):
        candidates = [{"name": "Microsoft Corp"}, {"name": "Google LLC"}]
        result = best_match("Zzzxyz Qqqabc", candidates, threshold=0.5)
        assert result is None

    def test_empty_candidates(self):
        assert best_match("Apple", []) is None

    def test_custom_name_key(self):
        candidates = [{"company": "Apple Inc"}]
        result = best_match("Apple", candidates, name_key="company")
        assert result["company"] == "Apple Inc"

    def test_skips_empty_names(self):
        candidates = [{"name": ""}, {"name": "Apple Inc"}]
        result = best_match("Apple", candidates)
        assert result["name"] == "Apple Inc"
