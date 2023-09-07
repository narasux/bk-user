# Generated by Django 3.2.20 on 2023-08-31 07:52

import bkuser.apps.data_source.constants
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data_source', '0002_inbuild_data_source_plugin'),
    ]

    operations = [
        migrations.AddField(
            model_name='datasource',
            name='creator',
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AddField(
            model_name='datasource',
            name='status',
            field=models.CharField(choices=[('enabled', '启用'), ('disabled', '未启用')], default=bkuser.apps.data_source.constants.DataSourceStatus['ENABLED'], max_length=32, verbose_name='数据源状态'),
        ),
        migrations.AddField(
            model_name='datasource',
            name='updater',
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AlterField(
            model_name='datasource',
            name='plugin_config',
            field=models.JSONField(default=dict, verbose_name='插件配置'),
        ),
        migrations.AlterField(
            model_name='datasource',
            name='sync_config',
            field=models.JSONField(default=dict, verbose_name='同步任务配置'),
        ),
    ]