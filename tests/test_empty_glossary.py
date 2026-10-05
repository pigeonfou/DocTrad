def test_empty_glossary_protects_only_real_technical_values():
    from app.quality import protect, restore
    source = "Power supply voltage: 12 VDC."
    for glossary in [None, {}]:
        protected, mapping = protect(source, glossary)
        assert list(mapping.values()) == ["12 VDC"]
        assert protected.startswith("Power supply voltage: ")
        assert restore(protected, mapping) == source
    protected, mapping = protect("Hello world.")
    assert protected == "Hello world."
    assert mapping == {}
