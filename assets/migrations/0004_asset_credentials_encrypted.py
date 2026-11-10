from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("assets", "0003_remindersettings_smtp_config")]
    operations = [migrations.AddField(model_name="asset", name="credentials_encrypted", field=models.TextField(blank=True))]