# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making 蓝鲸智云-用户管理(Bk-User) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from typing import Any, Dict

from bkuser.apps.data_source.models import DataSource
from bkuser.apps.data_source.plugins.constants import DATA_SOURCE_PLUGIN_CLASS_MAP, DATA_SOURCE_PLUGIN_CONFIG_CLASS_MAP
from bkuser.apps.sync.models import DataSourceSyncTask


class DataSourceSyncTaskRunner:
    def __init__(self, task: DataSourceSyncTask, context: Dict[str, Any]):
        self.task = task
        self.context = context
        self.overwrite = self.task.extra.get("overwrite", False)
        self.data_source = DataSource.objects.get(id=self.task.data_source_id)
        self._initial_plugin()

    def run(self):
        self._sync_users()
        self._sync_departments()

    def _initial_plugin(self):
        """初始化数据源插件"""
        plugin_config = self.data_source.plugin_config
        PluginCfgCls = DATA_SOURCE_PLUGIN_CONFIG_CLASS_MAP.get(self.data_source.plugin_id)  # noqa: N806
        if PluginCfgCls is not None:
            plugin_config = PluginCfgCls(**plugin_config)

        PluginCls = DATA_SOURCE_PLUGIN_CLASS_MAP[self.data_source.plugin_id]  # noqa: N806
        self.plugin = PluginCls(plugin_config, **self.context)

    def _sync_users(self):
        # TODO 字段映射，数据入库
        ...

    def _sync_departments(self):
        # TODO 数据入库（mptt 建树）
        ...
