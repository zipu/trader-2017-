# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2017-07-06 13:11
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('trading', '0005_product_is_favorite'),
    ]

    operations = [
        migrations.CreateModel(
            name='Equity',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('principal', models.DecimalField(decimal_places=2, max_digits=10)),
                ('profit', models.DecimalField(decimal_places=2, max_digits=10)),
            ],
        ),
        migrations.RemoveField(
            model_name='entry',
            name='comment',
        ),
        migrations.AddField(
            model_name='entry',
            name='code',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='trading.Code'),
        ),
    ]
