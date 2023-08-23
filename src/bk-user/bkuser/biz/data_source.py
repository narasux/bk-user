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
from collections import defaultdict
from typing import Dict, List, Optional

from pydantic import BaseModel

from bkuser.apps.data_source.models import DataSource, DataSourceDepartment, DataSourceDepartmentRelation


class DataSourceDepartmentInfoWithChildren(BaseModel):
    id: int
    name: str
    children: List[int]


class DataSourceSimpleInfo(BaseModel):
    id: int
    name: str


class DataSourceHandler:
    @staticmethod
    def get_data_source_map_by_owner(
        owner_tenant_ids: Optional[List[str]] = None,
    ) -> Dict[str, List[DataSourceSimpleInfo]]:
        """
        查询数据源
        """
        data_sources = DataSource.objects.all()
        if owner_tenant_ids is not None:
            data_sources = data_sources.filter(owner_tenant_id__in=owner_tenant_ids)

        data = defaultdict(list)
        for i in data_sources:
            data[i.owner_tenant_id].append(DataSourceSimpleInfo(id=i.id, name=i.name))

        return data

    @staticmethod
    def get_data_sources_by_tenant(tenant_ids: List[str]) -> Dict[str, List[int]]:
        # 当前属于租户的数据源
        tenant_data_source_map: Dict = {}
        data_sources = DataSource.objects.filter(owner_tenant_id__in=tenant_ids).values("id", "owner_tenant_id")
        for item in data_sources:
            tenant_id = item["owner_tenant_id"]
            if tenant_id in tenant_data_source_map:
                tenant_data_source_map[tenant_id].append(item["id"])
            else:
                tenant_data_source_map[tenant_id] = [item["id"]]
        # TODO 协同数据源获取
        return tenant_data_source_map


class DataSourceDepartmentHandler:
    @staticmethod
    def get_department_info_by_id(department_ids: List[int]) -> Dict[int, DataSourceDepartmentInfoWithChildren]:
        """
        获取部门基础信息
        """
        departments = DataSourceDepartment.objects.filter(id__in=department_ids)
        departments_map: Dict = {}
        for item in departments:
            children = DataSourceDepartmentRelation.objects.get(department=item).get_children()
            departments_map[item.id] = DataSourceDepartmentInfoWithChildren(
                id=item.id,
                name=item.name,
                children=list(children.values_list("department_id", flat=True)),
            )
        return departments_map
