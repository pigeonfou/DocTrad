import json
import pytest
from app import cli


def test_benchmark_uses_production_context_and_rejects_altered_units(monkeypatch, capsys, tmp_path):
    item = dict(id='opus', revision='a'*40, path=str(tmp_path), status='ready')
    monkeypatch.setattr(cli.Registry, 'list', lambda self: [item])
    monkeypatch.setattr(cli, 'CORPUS', ['Shadow Radio covers 26 miles.'])
    def post(url, *, headers, json, **kwargs):
        assert json['texts'] == cli.CORPUS
        assert json['contextual'] is True
        assert json['glossary']['Shadow Radio'] == 'Shadow Radio'
        return type('Response', (), {'status_code':200, 'json':lambda self: {'texts':['Shadow Radio couvre 26 kilomètres.']}})()
    import httpx
    monkeypatch.setattr(httpx, 'post', post)
    with pytest.raises(SystemExit, match='Benchmark technique échoué'):
        cli.model_action('benchmark', 'opus')
    score = json.loads(capsys.readouterr().out)
    assert score['inference_mode'] == 'contextual'
    assert score['technical_score'] == 0
    assert score['quality_score'] is None
