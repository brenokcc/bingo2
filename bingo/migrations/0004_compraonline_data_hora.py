# Generated by Django 4.2.4 on 2023-10-19 07:11

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('bingo', '0003_alter_compraonline_options_compraonline_email'),
    ]

    operations = [
        migrations.AddField(
            model_name='compraonline',
            name='data_hora',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now, verbose_name='Data/Hora'),
            preserve_default=False,
        ),
    ]
