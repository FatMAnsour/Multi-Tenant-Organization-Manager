# Full-text search support for User (PostgreSQL only)

from django.db import migrations


def create_gin_index(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
        CREATE INDEX IF NOT EXISTS core_user_search_gin
        ON users USING GIN (
            to_tsvector('english', coalesce(email, '') || ' ' || coalesce(full_name, ''))
        );
    """)


def drop_gin_index(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("DROP INDEX IF EXISTS core_user_search_gin;")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_gin_index, drop_gin_index),
    ]
