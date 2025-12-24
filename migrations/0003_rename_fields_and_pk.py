from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("warranty", "0002_safetyculturerecord_delete_examplemodel"),
    ]

    operations = [
        # rename existing columns from 0001 schema
        migrations.RenameField(
            model_name="safetyculturerecord",
            old_name="unit_serial_number",
            new_name="unit_sn",
        ),
        migrations.RenameField(
            model_name="safetyculturerecord",
            old_name="model",
            new_name="model_number",
        ),
        # make unit_sn unique first (so moving to PK is safe)
        migrations.AlterField(
            model_name="safetyculturerecord",
            name="unit_sn",
            field=models.CharField(max_length=100, unique=True),
        ),
        # drop the auto 'id' column
        migrations.RemoveField(
            model_name="safetyculturerecord",
            name="id",
        ),
        # promote unit_sn to primary key
        migrations.AlterField(
            model_name="safetyculturerecord",
            name="unit_sn",
            field=models.CharField(max_length=100, primary_key=True, serialize=False),
        ),
    ]
