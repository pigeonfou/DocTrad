from app.quality import protect, restore
from app.terminology import terminology

def test_radio_model_names_stay_unchanged():
    text = "The TrellisWare Shadow Radio works with a Ghost Radio and TSM-X."
    protected, mapping = protect(text, terminology())
    assert "Shadow Radio" not in protected
    assert "Ghost Radio" not in protected
    assert restore(protected, mapping) == text

def test_domain_glossary_translations():
    text = "Spatial Hops and Network Resilience"
    protected, mapping = protect(text, terminology())
    assert restore(protected, mapping) == "Sauts spatiaux and Résilience du réseau"

def test_user_glossary_has_precedence():
    text = "Spatial Hops"
    protected, mapping = protect(text, terminology({"Spatial Hops": "Relais spatiaux"}))
    assert restore(protected, mapping) == "Relais spatiaux"

def test_numeric_references_unchanged():
    text = "TSM-X supports 800 nodes in 1.2 MHz and AN/PRC-162."
    protected, mapping = protect(text, terminology())
    assert restore(protected, mapping) == text
