"""Password hashing (Argon2id)."""
try:
    from argon2 import PasswordHasher
    _ph = PasswordHasher()
    def hash_password(password: str) -> str:
        return _ph.hash(password)
    def verify_password(password: str, hashed: str) -> bool:
        try:
            _ph.verify(hashed, password)
            return True
        except Exception:
            return False
except ImportError:
    # Fallback for environments without argon2
    import hashlib
    def hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()
    def verify_password(password: str, hashed: str) -> bool:
        return hashlib.sha256(password.encode()).hexdigest() == hashed
