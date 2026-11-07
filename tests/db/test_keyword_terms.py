"""version-03 P11: keyword terms and rank fusion (pure functions; no database needed)."""

from sdlc_db.knowledge import RRF_K, fuse, keyword_terms, tsquery_text


def test_only_identifier_terms_are_searched():
    """K2 eval: plain words made the keyword ranking noisy; prose stays with the vector search."""
    terms = keyword_terms("Which runbook covers PAY-1234 and refund_manual_review in config.yaml?")
    assert terms == ["pay-1234", "refund_manual_review", "config.yaml"]
    assert keyword_terms("how does the refund worker retry failed refunds") == []
    assert keyword_terms("getUserToken from E1042, SEV1 rules") == ["getusertoken", "e1042", "sev1"]
    # plain acronyms are everywhere in this corpus (K2 on GCP dev): not searched
    assert keyword_terms("Which Entra claims does the MCP server check on GCP for PCI?") == []
    assert keyword_terms("MCP_PUBLIC_URL and OAuth2 on GCP") == ["mcp_public_url", "oauth2"]


def test_terms_are_safe_for_to_tsquery():
    terms = keyword_terms(r"x'); DROP TABLE chunks; -- 'inc-2031' a:b c\d")
    text = tsquery_text(terms)
    assert text == "'inc-2031'"  # DROP / TABLE are plain acronym-like words: not searched
    assert not any(c in text.replace("' | '", "").strip("'") for c in "();:\\")
    assert tsquery_text([]) == "" and tsquery_text(["bad'quote"]) == ""


def test_rrf_fusion_order():
    fused = fuse([1, 2, 3], [3, 4])
    assert [i for i, _, _ in fused] == [3, 1, 2, 4]  # 3 is in both rankings
    assert fused[0][2] == (0, 1) and fused[1][2] == (0,) and fused[-1][2] == (1,)
    assert fused[0][1] == 1 / (RRF_K + 3) + 1 / (RRF_K + 1)
    assert fuse([5, 6], [6, 5]) == fuse([5, 6], [6, 5])  # ties broken by best rank, then id
    assert [i for i, _, _ in fuse([5, 6], [6, 5])] == [5, 6]
