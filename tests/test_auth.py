import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from auth import verify_password, get_password_hash, create_access_token, authenticate_user, USERS_DB


class TestAuth:
    
    def test_hash_password(self):
        password = 'test_password'
        hashed = get_password_hash(password)
        assert isinstance(hashed, str)
        assert hashed != password
    
    def test_verify_password(self):
        password = 'test_password'
        hashed = get_password_hash(password)
        result = verify_password(password, hashed)
        assert result is True
    
    def test_verify_wrong_password(self):
        password = 'test_password'
        hashed = get_password_hash(password)
        result = verify_password('wrong_password', hashed)
        assert result is False
    
    def test_create_access_token(self):
        token = create_access_token({'sub': 'admin'})
        assert isinstance(token, str)
        assert len(token) > 0