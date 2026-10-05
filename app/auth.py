import secrets
import time
from collections import defaultdict, deque
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import HTTPException
from .db import User

hasher = PasswordHasher()
attempts = defaultdict(deque)

def password_hash(password):
    if len(password) < 12: raise ValueError("Mot de passe : 12 caractères minimum")
    return hasher.hash(password)

def verify(stored, password):
    try: return hasher.verify(stored, password)
    except VerificationError: return False

def csrf(request, token):
    expected = request.session.get("csrf", "")
    if not expected or not secrets.compare_digest(expected, token): raise HTTPException(403, "Jeton de formulaire invalide")

def authenticated(request, db):
    user = db.get(User, request.session.get("uid", -1))
    if not user: raise HTTPException(401, "Connexion nécessaire")
    return user

def rate_limit(key):
    entries = attempts[key]
    now = time.monotonic()
    while entries and now - entries[0] > 300: entries.popleft()
    if len(entries) >= 10: raise HTTPException(429, "Trop de tentatives ; réessayez dans cinq minutes")
    entries.append(now)
