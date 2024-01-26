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
from django.urls import path

from bkuser.apis.web.data_source_organization import views

urlpatterns = [
    # 数据源用户列表
    path("<int:id>/users/", views.DataSourceUserListCreateApi.as_view(), name="data_source_user.list_create"),
    # 获取数据源用户用于 Leader 下拉框
    path("<int:id>/leaders/", views.DataSourceLeadersListApi.as_view(), name="data_source_leader.list"),
    # 获取数据源部门用户部门下拉框
    path("<int:id>/departments/", views.DataSourceDepartmentsListApi.as_view(), name="data_source_department.list"),
    # 数据源用户
    path(
        "users/<int:id>/",
        views.DataSourceUserRetrieveUpdateDestroyApi.as_view(),
        name="data_source_user.retrieve_update_destroy",
    ),
    # 切换数据源用户状态（启/停）
    path(
        "users/<int:id>/operations/switch_status/",
        views.DataSourceUserSwitchStatusApi.as_view(),
        name="data_source_user.switch_status",
    ),
    # 重置本地数据源用户密码（租户管理员操作）
    path(
        "users/<int:id>/password/",
        views.DataSourceUserPasswordResetApi.as_view(),
        name="data_source_user.password.reset",
    ),
    # 获取数据源用户所属部门组织路径
    path(
        "users/<int:id>/organization-paths/",
        views.DataSourceUserOrganizationPathListApi.as_view(),
        name="data_source_user.organization_path.list",
    ),
    # 切换数据源部门状态（启/停）
    path(
        "departments/<int:id>/operations/switch_status/",
        views.DataSourceDepartmentSwitchStatusApi.as_view(),
        name="data_source_department.switch_status",
    ),
]
