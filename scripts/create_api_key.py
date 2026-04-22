from __future__ import annotations

import argparse
from pathlib import Path

from ptsd_support.services.auth import add_user_membership, create_api_token, create_organization, create_user


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or update a backend user and issue an API token.")
    parser.add_argument("--db", required=True, help="Database path.")
    parser.add_argument("--user-key", required=True, help="Stable user key.")
    parser.add_argument("--display-name", required=True, help="Display name.")
    parser.add_argument("--role", choices=["viewer", "clinician", "admin"], required=True)
    parser.add_argument("--label", default="default", help="Token label.")
    parser.add_argument("--org-key", help="Optional organization key to create/use and set as default membership.")
    parser.add_argument("--org-name", help="Optional organization name when creating --org-key.")
    args = parser.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    user = create_user(
        db_path,
        user_key=args.user_key,
        display_name=args.display_name,
        role=args.role,
    )
    if args.org_key:
        create_organization(
            db_path,
            org_key=args.org_key,
            name=args.org_name or args.org_key.replace("-", " ").title(),
        )
        add_user_membership(
            db_path,
            user_key=args.user_key,
            org_key=args.org_key,
            membership_role=args.role,
            is_default=True,
        )
    token = create_api_token(
        db_path,
        user_key=args.user_key,
        label=args.label,
    )
    print({"user": user, "token": token["token"], "token_prefix": token["token_prefix"]})


if __name__ == "__main__":
    main()
