import hashlib,json
from app.registry import Registry

def manifest(tmp_path, **changes):
    directory=tmp_path/'opus';directory.mkdir()
    for name in ['config.json','model.safetensors']: (directory/name).write_bytes(b'fixture')
    m=dict(id='opus',name='OPUS',family='opus',revision='a'*40,license='apache-2.0',usage_policy='permissive',profile='light',enabled=True,sha256={name:hashlib.sha256(b'fixture').hexdigest() for name in ['config.json','model.safetensors']})
    m.update(changes);(directory/'manifest.json').write_text(json.dumps(m));return directory

def test_registry_local(tmp_path):
    manifest(tmp_path)
    assert Registry(tmp_path).choose()['id']=='opus'

def test_checksum_fails(tmp_path):
    path=manifest(tmp_path);(path/'config.json').write_text('tampered')
    import pytest
    with pytest.raises(ValueError):Registry(tmp_path).choose()

def test_license_restricted_is_informational(tmp_path):
    manifest(tmp_path,usage_policy='non-commercial',license='cc-by-nc-4.0')
    assert Registry(tmp_path).choose()['license']=='cc-by-nc-4.0'

def test_license_missing_is_allowed(tmp_path):
    manifest(tmp_path,license=None,usage_policy=None)
    assert Registry(tmp_path).choose()['id']=='opus'

def test_disabled_not_selected(tmp_path):
    manifest(tmp_path,enabled=False)
    import pytest
    with pytest.raises(ValueError):Registry(tmp_path).choose()

