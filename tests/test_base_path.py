import importlib
from fastapi.testclient import TestClient


def test_prefixed_login_forms_assets_and_redirects(monkeypatch):
    monkeypatch.setenv('DOCTRAD_BASE_PATH','/doctrad')
    from app import web
    importlib.reload(web)
    try:
        with TestClient(web.app, base_url='http://www.pigeonfou.com', follow_redirects=False) as client:
            response=client.get('/doctrad/')
            assert response.status_code==303
            assert response.headers['location']=='/doctrad/login'
            response=client.get('/doctrad/login')
            assert response.status_code==200
            assert '/doctrad/static/app.js' in response.text
            assert 'doctrad_session=' in response.headers['set-cookie']
            assert 'path=/doctrad/' in response.headers['set-cookie']
            assert client.get('/doctrad/static/app.js').status_code==200
            import re
            from app.db import Session, User
            from app.auth import password_hash
            with Session.begin() as db:
                db.add(User(username='prefixadmin', password=password_hash('prefix-password-123'), admin=True))
            token=re.search(r'name="token" value="([^"]+)"', response.text).group(1)
            response=client.post('/doctrad/login',data={'username':'prefixadmin','password':'prefix-password-123','token':token})
            assert response.status_code==303 and response.headers['location']=='/doctrad/'
            response=client.get('/doctrad/')
            assert response.status_code==200 and 'action="/doctrad/jobs"' in response.text
            assert client.get('/doctrad/glossary').status_code==200
            page=client.get('/doctrad/admin')
            assert 'action="/doctrad/admin/models/download"' in page.text
            token=re.search(r'name="token" value="([^"]+)"', page.text).group(1)
            from unittest.mock import patch
            with patch('app.model_download.start_download',return_value='job'):
                response=client.post('/doctrad/admin/models/download',data={'model_id':'opus-mt-en-fr','token':token,'confirm_network':'yes'})
                assert response.status_code==303 and response.headers['location']=='/doctrad/admin'
            assert client.get('/doctrad/admin/models/download/status').status_code==200
            assert client.get('/cableplan/health').status_code==404
    finally:
        monkeypatch.delenv('DOCTRAD_BASE_PATH')
        importlib.reload(web)
