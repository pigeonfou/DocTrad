import pytest
from fastapi import HTTPException
from app.auth import rate_limit


def test_login_limit_remains_active_within_each_test():
    for _ in range(10):
        rate_limit('same-client')
    with pytest.raises(HTTPException) as error:
        rate_limit('same-client')
    assert error.value.status_code == 429
    rate_limit('different-client')
