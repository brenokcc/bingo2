# Generated by Django 4.2.4 on 2023-10-18 19:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bingo', '0002_compraonline'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='compraonline',
            options={'verbose_name': 'Compra Online', 'verbose_name_plural': 'Compras Online'},
        ),
        migrations.AddField(
            model_name='compraonline',
            name='email',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='E-mail'),
        ),
    ]
