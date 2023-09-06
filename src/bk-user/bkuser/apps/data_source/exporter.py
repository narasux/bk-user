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
from django.conf import settings
from openpyxl.reader.excel import load_workbook
from openpyxl.workbook import Workbook

from bkuser.apps.data_source.models import DataSource


class DataSourceOrgExporter:
    """导出数据源用户 & 组织信息"""

    def __init__(self, data_source: DataSource):
        self.data_source = data_source

    def gen_template(self) -> Workbook:
        # TODO (su) 支持获取并导出动态字段
        return load_workbook(settings.EXPORT_ORG_TEMPLATE)

    def export(self) -> Workbook:
        return self.gen_template()
        # TODO (su) 从 DB 中获取数据填充到 xlsx 中
