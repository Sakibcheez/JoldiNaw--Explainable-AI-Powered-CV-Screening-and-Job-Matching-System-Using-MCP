"""Explicit admin command: map a verified OIDC subject to a stored organization membership."""

import argparse
from sqlalchemy import select
from app.db import Membership, Organization, Session, User, uid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--organization", required=True, help="Existing organization ID, or name with --create-org")
    parser.add_argument("--create-org", action="store_true")
    parser.add_argument("--role", choices=["admin", "recruiter", "viewer"], default="recruiter")
    args = parser.parse_args()
    with Session() as db:
        org = (
            Organization(id=uid(), name=args.organization)
            if args.create_org
            else db.get(Organization, args.organization)
        )
        if org is None:
            raise ValueError("Organization not found")
        db.add(org)
        user = db.scalar(select(User).where(User.subject == args.subject))
        if user is None:
            user = User(id=uid(), subject=args.subject)
            db.add(user)
        db.flush()
        membership = db.get(Membership, (org.id, user.id))
        if membership:
            membership.role = args.role
        else:
            db.add(Membership(organization_id=org.id, user_id=user.id, role=args.role))
        db.commit()
        print(f"Provisioned membership in organization {org.id}")


if __name__ == "__main__":
    main()
