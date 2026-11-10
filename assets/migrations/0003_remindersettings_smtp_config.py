from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("assets", "0002_default_workspace")]
    operations = [migrations.AddField(model_name="remindersettings", name="smtp_config", field=models.TextField(blank=True))]