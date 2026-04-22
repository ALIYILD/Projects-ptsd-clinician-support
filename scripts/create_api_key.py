from __future__ import annotations

import argparse
from pathlib import Path

from ptsd_support.services.auth import create_api_token, create_user


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or update a backend user and issue an API token.")
    parser.add_argument("--db", required=True, help="Database path.")
    parser.add_argument("--user-key", required=True, help="Stable user key.")
    parser.add_argument("--display-name", required=True, help="Display name.")
    parser.add_argument("--role", choices=["viewer", "clinician", "admin"], required=True)
    parser.add_argument("--label", default="default", help="Token label.")
    args = parser.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    user = create_user(
        db_path,
        user_key=args.user_key,
        display_name=args.display_name,
        role=args.role,
    )
    token = create_api_token(
        db_path,
        user_key=args.user_key,
        label=args.label,
    )
    print({"user": user, "token": token["token"], "token_prefix": token["token_prefix"]})


if __name__ == "__main__":
    main()
