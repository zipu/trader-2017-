# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2017-07-02 12:18
from __future__ import unicode_literals

import datetime
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Account',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(blank=True, null=True)),
                ('krw', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('usd', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('euro', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Code',
            fields=[
                ('code', models.CharField(max_length=10, primary_key=True, serialize=False)),
                ('month', models.DateField()),
                ('ec_price', models.DecimalField(decimal_places=7, max_digits=20)),
            ],
        ),
        migrations.CreateModel(
            name='Entry',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('entry_date', models.DateTimeField()),
                ('contracts', models.PositiveSmallIntegerField(default=1)),
                ('entry_price', models.DecimalField(decimal_places=7, max_digits=20)),
                ('loss_cut', models.DecimalField(decimal_places=7, max_digits=20)),
                ('plan', models.CharField(blank=True, max_length=50, null=True)),
                ('comment', models.CharField(blank=True, max_length=100, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Exit',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('exit_date', models.DateTimeField()),
                ('contracts', models.PositiveSmallIntegerField(default=1)),
                ('exit_price', models.DecimalField(decimal_places=7, max_digits=20)),
                ('profit', models.DecimalField(blank=True, decimal_places=3, max_digits=20)),
                ('profit_per_contract', models.DecimalField(blank=True, decimal_places=3, max_digits=20, null=True)),
                ('commission', models.DecimalField(blank=True, decimal_places=2, max_digits=5)),
                ('holding_period', models.DurationField(blank=True)),
                ('ptr_ratio', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('entry', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='trading.Entry')),
            ],
        ),
        migrations.CreateModel(
            name='Game',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pub_date', models.DateField(default=datetime.date.today)),
                ('name', models.CharField(blank=True, max_length=50)),
                ('position', models.IntegerField(choices=[(1, 'Long'), (-1, 'Short')])),
                ('profit', models.DecimalField(blank=True, decimal_places=3, max_digits=20, null=True)),
                ('profit_per_contract', models.DecimalField(blank=True, decimal_places=3, max_digits=20, null=True)),
                ('commission', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('is_completed', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                ('name', models.CharField(max_length=50, unique=True)),
                ('group', models.CharField(max_length=30, primary_key=True, serialize=False, unique=True)),
                ('market', models.CharField(max_length=10)),
                ('active', models.CharField(blank=True, max_length=10, null=True)),
                ('front', models.CharField(blank=True, max_length=10, null=True)),
                ('activated_date', models.DateField(blank=True, null=True)),
                ('price_gap', models.DecimalField(blank=True, decimal_places=7, max_digits=20, null=True)),
                ('currency', models.CharField(max_length=10)),
                ('open_margin', models.DecimalField(decimal_places=2, max_digits=10)),
                ('keep_margin', models.DecimalField(decimal_places=2, max_digits=10)),
                ('open_time', models.TimeField()),
                ('close_time', models.TimeField()),
                ('tick_unit', models.DecimalField(decimal_places=7, max_digits=20)),
                ('tick_value', models.DecimalField(decimal_places=3, max_digits=20)),
                ('commission', models.DecimalField(decimal_places=2, max_digits=5)),
                ('notation', models.PositiveSmallIntegerField()),
                ('decimal_places', models.PositiveSmallIntegerField()),
                ('last_update', models.DateTimeField()),
            ],
        ),
        migrations.AddField(
            model_name='game',
            name='product',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='trading.Product'),
        ),
        migrations.AddField(
            model_name='exit',
            name='game',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='trading.Game'),
        ),
        migrations.AddField(
            model_name='entry',
            name='game',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='trading.Game'),
        ),
        migrations.AddField(
            model_name='code',
            name='product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='trading.Product'),
        ),
    ]
