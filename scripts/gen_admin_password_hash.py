import getpass
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def main():
    password = getpass.getpass("Admin password: ")
    if not password:
        raise SystemExit("password is required")
    print(pwd_context.hash(password))


if __name__ == "__main__":
    main()
