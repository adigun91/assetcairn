from django.db import migrations


def create_defaults(apps, schema_editor):
    role = apps.get_model("assets", "Role")
    for name, permissions in [
        ("Administrator", ["assets:write", "users:manage", "roles:manage", "reminders:manage"]),
        ("Asset Manager", ["assets:write"]),
        ("Viewer", []),
    ]:
        role.objects.get_or_create(name=name, defaults={"permissions": permissions, "system": True})
    apps.get_model("assets", "ReminderSettings").objects.get_or_create(pk=1)
    apps.get_model("assets", "SetupLock").objects.get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [("assets", "0001_initial")]
    operations = [migrations.RunPython(create_defaults, migrations.RunPython.noop)]