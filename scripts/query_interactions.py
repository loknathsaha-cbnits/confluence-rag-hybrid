#!/usr/bin/env python3
"""
Utility script to query interactions from the SQLite database.
Usage:
    python scripts/query_interactions.py --user loknath_saha_2004 --limit 10
    python scripts/query_interactions.py --analytics
    python scripts/query_interactions.py --session <session_id>
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db import get_db_manager


def format_datetime(dt_string):
    """Format datetime string for display."""
    try:
        dt = datetime.fromisoformat(dt_string)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return dt_string


def print_interaction(interaction):
    """Pretty print an interaction record."""
    print("\n" + "=" * 80)
    print(f"Interaction ID: {interaction['interaction_id']}")
    print(f"Created: {format_datetime(interaction['created_at'])}")
    print(f"Processing Time: {interaction['processing_time_ms']}ms")
    print("-" * 80)
    print(f"Query: {interaction['query']}")
    print("-" * 80)
    print(f"Answer: {interaction['answer'][:200]}{'...' if len(interaction['answer']) > 200 else ''}")
    print("-" * 80)
    print(f"Confidence Score: {interaction['confidence_score']:.2%}")

    if interaction['sources']:
        print(f"Sources ({len(interaction['sources'])}):")
        for i, source in enumerate(interaction['sources'], 1):
            print(f"  {i}. {source['title']}")
            print(f"     URL: {source['url']}")


def query_by_user(user_id, limit):
    """Query interactions by user ID."""
    db = get_db_manager()
    interactions = db.get_interaction_history(user_id, limit)

    print(f"\n📊 Showing {len(interactions)} interactions for user: {user_id}")

    for interaction in interactions:
        print_interaction(interaction)

    print("\n" + "=" * 80)
    print(f"✅ Total interactions retrieved: {len(interactions)}")


def query_by_session(session_id):
    """Query interactions by session ID."""
    db = get_db_manager()
    interactions = db.get_session_interactions(session_id)

    print(f"\n📊 Showing {len(interactions)} interactions in session: {session_id}")

    for interaction in interactions:
        print_interaction(interaction)

    print("\n" + "=" * 80)
    print(f"✅ Total interactions in session: {len(interactions)}")


def show_analytics(user_id=None):
    """Show analytics about interactions."""
    db = get_db_manager()
    stats = db.get_analytics(user_id)

    print("\n📊 Analytics Report")
    print("=" * 80)

    if user_id:
        print(f"User: {user_id}")
    else:
        print("Scope: All Users")

    print("-" * 80)
    print(f"Total Interactions: {stats['total_interactions']}")
    print(f"Average Confidence: {stats['average_confidence']:.3f} (out of 1.0)")
    print(f"Average Processing Time: {stats['average_processing_time_ms']:.2f}ms")
    print(f"Success Rate: {stats['success_rate']:.2f}%")
    print("=" * 80)


def list_all_users():
    """List all users in the database."""
    db = get_db_manager()
    conn = db._get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT u.user_id, COUNT(i.interaction_id) as interaction_count,
               MAX(u.last_active) as last_active
        FROM users u
        LEFT JOIN interactions i ON u.user_id = i.user_id
        GROUP BY u.user_id
        ORDER BY interaction_count DESC
    """)

    rows = cursor.fetchall()

    print("\n👥 Users in Database")
    print("=" * 80)
    print(f"{'User ID':<30} {'Interactions':<15} {'Last Active':<30}")
    print("-" * 80)

    for row in rows:
        user_id = row[0]
        count = row[1] or 0
        last_active = format_datetime(row[2]) if row[2] else "Never"
        print(f"{user_id:<30} {count:<15} {last_active:<30}")

    print("=" * 80)
    print(f"✅ Total users: {len(rows)}")


def export_to_json(user_id, output_file):
    """Export interactions to JSON file."""
    db = get_db_manager()
    interactions = db.get_interaction_history(user_id, limit=1000)

    # Convert datetime objects to strings
    for interaction in interactions:
        interaction['created_at'] = format_datetime(interaction['created_at'])

    with open(output_file, 'w') as f:
        json.dump(interactions, f, indent=2)

    print(f"✅ Exported {len(interactions)} interactions to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Query OpsEngine interaction database"
    )

    parser.add_argument(
        '--user',
        help='Query by user ID',
        type=str
    )
    parser.add_argument(
        '--session',
        help='Query by session ID',
        type=str
    )
    parser.add_argument(
        '--limit',
        help='Limit number of results',
        type=int,
        default=10
    )
    parser.add_argument(
        '--analytics',
        help='Show analytics',
        action='store_true'
    )
    parser.add_argument(
        '--user-analytics',
        help='Show analytics for specific user',
        type=str
    )
    parser.add_argument(
        '--list-users',
        help='List all users',
        action='store_true'
    )
    parser.add_argument(
        '--export',
        help='Export user interactions to JSON',
        type=str,
        metavar='OUTPUT_FILE'
    )
    parser.add_argument(
        '--export-user',
        help='User ID for export (use with --export)',
        type=str
    )

    args = parser.parse_args()

    try:
        if args.list_users:
            list_all_users()
        elif args.user:
            query_by_user(args.user, args.limit)
        elif args.session:
            query_by_session(args.session)
        elif args.user_analytics:
            show_analytics(args.user_analytics)
        elif args.analytics:
            show_analytics()
        elif args.export and args.export_user:
            export_to_json(args.export_user, args.export)
        else:
            # Default: show analytics for all users
            show_analytics()
            print("\n💡 Use --user <user_id> to see specific user interactions")
            print("💡 Use --list-users to see all users")
            print("💡 Use --help for more options")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
