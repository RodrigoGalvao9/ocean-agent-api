from src.core.sources import SourceRecorder


def _payload(**kw):
    base = {"status": "ok", "source": "Fonte A", "retrieved_at": "2026-11-21T12:00:00Z"}
    return {**base, **kw}


def test_records_provenance_fields():
    r = SourceRecorder()
    r.record(
        "get_tide_table",
        _payload(
            source_url="https://x",
            freshness="reference",
            data_timestamp="2026-11-22T00:00:00Z",
            limitations=["só maré astronômica", 3],
        ),
    )
    (s,) = r.sources
    assert (s.tool, s.name, s.url, s.freshness) == ("get_tide_table", "Fonte A", "https://x", "reference")
    assert s.data_timestamp == "2026-11-22T00:00:00Z"
    assert s.limitations == ["só maré astronômica"]  # item inválido é descartado


def test_ignores_payloads_without_source_and_unavailable_ones():
    r = SourceRecorder()
    r.record("t", {"text": "sem contrato"})
    r.record("t", ["lista"])
    r.record("t", None)
    r.record("t", _payload(status="unavailable"))
    assert r.sources == []


def test_deduplicates_by_name_and_url():
    r = SourceRecorder()
    r.record("a", _payload())
    r.record("b", _payload())
    r.record("c", _payload(source_url="https://y"))
    assert [s.tool for s in r.sources] == ["a", "c"]


def test_attribution_footer_is_unique_and_empty_when_not_required():
    r = SourceRecorder()
    assert r.attribution_footer() == ""
    r.record("a", _payload(attribution="Open-Meteo.com (CC BY 4.0)"))
    r.record("b", _payload(source="Fonte B", attribution="Open-Meteo.com (CC BY 4.0)"))
    r.record("c", _payload(source="Fonte C", attribution="Global Fishing Watch"))
    assert r.attribution_footer() == "\n\nAtribuição: Open-Meteo.com (CC BY 4.0); Global Fishing Watch"
