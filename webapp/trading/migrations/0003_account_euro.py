# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2017-07-02 16:32
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trading', '0002_remove_account_euro'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='euro',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]