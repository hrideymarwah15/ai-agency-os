"""Generate Argon2id password hashes for OWNER_PASSWORD_HASH (D-16)."""

import argparse
import getpass
import sys

from pwdlib import PasswordHash


def main() -> int:
    """Run the CLI; return a process exit code."""
    parser = argparse.ArgumentParser(
        prog="hash_password",
        description="Generate an Argon2id hash for OWNER_PASSWORD_HASH in .env",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("hash", help="hash a password read from stdin")
    args = parser.parse_args()

    if args.command == "hash":
        password = getpass.getpass("Password: ")
        if not password:
            print("error: password must not be empty", file=sys.stderr)
            return 1
        print(PasswordHash.recommended().hash(password))
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
