from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import secrets


def generate_password_hash(password: str, iterations: int = 260_000, salt: str | None = None) -> str:
    if not password:
        raise ValueError("Password must not be empty.")
    if iterations < 100_000:
        raise ValueError("Iterations must be at least 100000.")

    use_salt = salt or secrets.token_urlsafe(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        use_salt.encode("utf-8"),
        iterations,
    )
    digest_b64 = base64.b64encode(derived).decode("utf-8")
    return f"pbkdf2_sha256${iterations}${use_salt}${digest_b64}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate ADMIN_PASSWORD_HASH for backend auth.")
    parser.add_argument("--password", help="Admin password (omit to enter securely).")
    parser.add_argument("--iterations", type=int, default=260_000, help="PBKDF2 iterations.")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Admin password: ")
    encoded = generate_password_hash(password=password, iterations=args.iterations)
    print(encoded)


if __name__ == "__main__":
    main()
