#!/usr/bin/env python3
"""
Inventory management script.

Subcommands:
    import   - Import inventory.yml to ORM database
    update   - Update host fields (port, password, old_password, user, private_key)
    remove   - Remove a host from inventory
    list     - List all hosts

Usage:
    python3 bin/inventory.py import
    python3 bin/inventory.py update --host 192.168.1.10 --port 2222
    python3 bin/inventory.py update --host 192.168.1.10 \
        --user admin --password 'Pass123!'
    python3 bin/inventory.py remove --host 192.168.1.10
    python3 bin/inventory.py list
"""

import argparse
import json
import logging
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.resolve()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Completely disable ALL logging BEFORE importing any lib modules!
logging.disable(logging.CRITICAL)

from lib.database import Database, Inventory  # noqa: E402


def get_inventory(db: Database) -> Inventory:
    """Create Inventory instance with default paths."""
    return Inventory(db, inventory_path=BASE_DIR / "etc" / "inventory.yml")


def cmd_import(_args: argparse.Namespace) -> int:
    """Import inventory.yml to ORM."""
    db = Database(BASE_DIR / "logs" / "tsc_ansible_mcp.db")
    inventory = get_inventory(db)
    result = inventory.import_from_yaml()
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "success" else 1


def cmd_update(args: argparse.Namespace) -> int:
    """Update host fields."""
    db = Database(BASE_DIR / "logs" / "tsc_ansible_mcp.db")
    inventory = get_inventory(db)

    user: str | None = args.user
    port: int | None = args.port
    password: str | None = args.password
    old_password: str | None = args.old_password
    private_key: str | None = args.private_key

    if (
        port is None
        and user is None
        and password is None
        and old_password is None
        and private_key is None
    ):
        print(
            "Error: At least one field must be specified "
            "(--port, --user, --password, --old-password, --private_key)",
            file=sys.stderr,
        )
        return 1

    result = inventory.update_host_credentials(
        args.host,
        user=user,
        port=port,
        password=password,
        old_password=old_password,
        private_key=private_key,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "success" else 1


def cmd_remove(args: argparse.Namespace) -> int:
    """Remove a host."""
    db = Database(BASE_DIR / "logs" / "tsc_ansible_mcp.db")
    inventory = get_inventory(db)
    result = inventory.remove_host(args.host)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "success" else 1


def cmd_list(_args: argparse.Namespace) -> int:
    """List all hosts."""
    db = Database(BASE_DIR / "logs" / "tsc_ansible_mcp.db")
    inventory = get_inventory(db)
    hosts = inventory.get_all_hosts()
    print(json.dumps(hosts, indent=2))
    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Inventory management script")
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to run")

    # import subcommand
    import_parser = subparsers.add_parser("import", help="Import inventory.yml to ORM")
    import_parser.set_defaults(func=cmd_import)

    # update subcommand
    update_parser = subparsers.add_parser("update", help="Update host fields")
    update_parser.add_argument("--host", required=True, help="Host IP or hostname")
    update_parser.add_argument("--port", type=int, help="New SSH port")
    update_parser.add_argument("--user", help="New SSH user")
    update_parser.add_argument("--password", help="New SSH password")
    update_parser.add_argument(
        "--old-password", dest="old_password", help="Previous SSH password"
    )
    update_parser.add_argument(
        "--private-key", dest="private_key", help="SSH private key path"
    )
    update_parser.set_defaults(func=cmd_update)

    # remove subcommand
    remove_parser = subparsers.add_parser("remove", help="Remove a host")
    remove_parser.add_argument("--host", required=True, help="Host IP or hostname")
    remove_parser.set_defaults(func=cmd_remove)

    # list subcommand
    list_parser = subparsers.add_parser("list", help="List all hosts")
    list_parser.set_defaults(func=cmd_list)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
