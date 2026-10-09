from unittest.mock import patch

def test_api_key_form_admin_csrf_and_never_echoes_secret(client):
    from test_web import signin
    token = signin(client)
    with patch("app.remote_ai.save_api_key") as save:
        response = client.post("/admin/remote-ai/key", data={"token":token,"api_key":"private-test-key"})
        assert response.status_code == 403
        save.assert_not_called()
    client.cookies.clear()
    token = signin(client, name="admin", admin=True)
    page = client.get("/admin").text
    assert 'type="password" name="api_key"' in page
    with patch("app.remote_ai.save_api_key") as save:
        response = client.post("/admin/remote-ai/key", data={"token":"invalid","api_key":"private-test-key"})
        assert response.status_code == 403
        save.assert_not_called()
        response = client.post("/admin/remote-ai/key", data={"token":token,"api_key":"private-test-key"}, follow_redirects=False)
        assert response.status_code == 303
        save.assert_called_once_with("private-test-key")
        assert "private-test-key" not in response.text
        assert "private-test-key" not in client.get("/admin?remote_saved=1").text
