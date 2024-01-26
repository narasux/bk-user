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
from typing import List

from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from bkuser.apis.web.data_source_organization.serializers import (
    DataSourceDepartmentSwitchStatusOutputSLZ,
    DataSourceUserOrganizationPathOutputSLZ,
    DataSourceUserPasswordResetInputSLZ,
    DataSourceUserSwitchStatusOutputSLZ,
    DepartmentSearchInputSLZ,
    DepartmentSearchOutputSLZ,
    LeaderSearchInputSLZ,
    LeaderSearchOutputSLZ,
    UserCreateInputSLZ,
    UserRetrieveOutputSLZ,
    UserSearchInputSLZ,
    UserSearchOutputSLZ,
    UserUpdateInputSLZ,
)
from bkuser.apis.web.mixins import CurrentUserTenantMixin
from bkuser.apps.data_source.constants import DataSourceDepartmentStatus, DataSourceStatus, DataSourceUserStatus
from bkuser.apps.data_source.models import (
    DataSource,
    DataSourceDepartment,
    DataSourceDepartmentRelation,
    DataSourceDepartmentUserRelation,
    DataSourceUser,
)
from bkuser.apps.notification.tasks import send_reset_password_to_user
from bkuser.apps.permission.constants import PermAction
from bkuser.apps.permission.permissions import perm_class
from bkuser.apps.tenant.constants import TenantDepartmentStatus, TenantUserStatus
from bkuser.apps.tenant.models import TenantDepartment, TenantUser
from bkuser.biz.data_source_organization import (
    DataSourceUserEditableInfo,
    DataSourceUserHandler,
    DataSourceUserInfo,
    DataSourceUserRelationInfo,
)
from bkuser.common.error_codes import error_codes
from bkuser.common.views import ExcludePatchAPIViewMixin, ExcludePutAPIViewMixin


class DataSourceUserListCreateApi(CurrentUserTenantMixin, generics.ListCreateAPIView):
    serializer_class = UserSearchOutputSLZ
    lookup_url_kwarg = "id"
    permission_classes = [IsAuthenticated, perm_class(PermAction.MANAGE_TENANT)]

    def get_queryset(self):
        slz = UserSearchInputSLZ(data=self.request.query_params)
        slz.is_valid(raise_exception=True)
        data = slz.validated_data
        data_source_id = self.kwargs["id"]

        # 数据源处于启用 / 停用状态下都可以查询用户，但是软删除状态下不行
        data_source = DataSource.objects.filter(
            id=data_source_id,
            owner_tenant_id=self.get_current_tenant_id(),
            status__in=[DataSourceStatus.ENABLED, DataSourceStatus.DISABLED],
        ).first()
        if not data_source:
            raise error_codes.DATA_SOURCE_NOT_EXISTS

        queryset = DataSourceUser.objects.filter(
            data_source=data_source,
            status__in=[DataSourceUserStatus.ENABLED, DataSourceUserStatus.DISABLED],
        )
        if username := data.get("username"):
            queryset = queryset.filter(username__icontains=username)

        return queryset

    @swagger_auto_schema(
        tags=["data_source_organization"],
        operation_description="数据源用户列表",
        query_serializer=UserSearchInputSLZ(),
        responses={status.HTTP_200_OK: UserSearchOutputSLZ(many=True)},
    )
    def get(self, request, *args, **kwargs):
        # 数据源用户是强制分页的，因此这里直接取分页数据
        data_source_users = self.paginate_queryset(self.get_queryset())

        user_dept_infos_map = defaultdict(list)
        for rel in DataSourceDepartmentUserRelation.objects.filter(
            user_id__in=[u.id for u in data_source_users]
        ).select_related("department"):
            user_dept_infos_map[rel.user_id].append({"id": rel.department_id, "name": rel.department.name})

        slz = UserSearchOutputSLZ(data_source_users, many=True, context={"user_dept_infos_map": user_dept_infos_map})
        return self.get_paginated_response(slz.data)

    @swagger_auto_schema(
        tags=["data_source_organization"],
        operation_description="新建数据源用户",
        request_body=UserCreateInputSLZ(),
        responses={status.HTTP_201_CREATED: ""},
    )
    def post(self, request, *args, **kwargs):
        # 只有已经启用的数据源才可以新增用户
        data_source = DataSource.objects.filter(id=self.kwargs["id"], status=DataSourceStatus.ENABLED).first()
        if not data_source:
            raise error_codes.DATA_SOURCE_NOT_ENABLED

        # 不允许对非本地数据源进行用户新增操作
        if not data_source.is_local:
            raise error_codes.DATA_SOURCE_USER_CREATE_FAILED

        slz = UserCreateInputSLZ(
            data=request.data,
            context={
                "tenant_id": self.get_current_tenant_id(),
                "data_source_id": data_source.id,
            },
        )
        slz.is_valid(raise_exception=True)
        data = slz.validated_data

        # 校验是否已存在该用户
        if DataSourceUser.objects.filter(username=data["username"], data_source=data_source).exists():
            raise error_codes.DATA_SOURCE_USER_ALREADY_EXISTED

        user_info = DataSourceUserInfo(
            username=data["username"],
            full_name=data["full_name"],
            email=data["email"],
            phone=data["phone"],
            phone_country_code=data["phone_country_code"],
            logo=data["logo"],
            extras=data["extras"],
        )
        relation_info = DataSourceUserRelationInfo(
            department_ids=data["department_ids"], leader_ids=data["leader_ids"]
        )
        DataSourceUserHandler.create_user(data_source, user_info, relation_info)
        return Response(status=status.HTTP_201_CREATED)


class DataSourceLeadersListApi(CurrentUserTenantMixin, generics.ListAPIView):
    serializer_class = LeaderSearchOutputSLZ
    permission_classes = [IsAuthenticated, perm_class(PermAction.MANAGE_TENANT)]

    def get_queryset(self):
        slz = LeaderSearchInputSLZ(data=self.request.query_params)
        slz.is_valid(raise_exception=True)
        data = slz.validated_data

        # 校验数据源是否存在且处于启用的状态
        data_source = DataSource.objects.filter(
            owner_tenant_id=self.get_current_tenant_id(), id=self.kwargs["id"], status=DataSourceStatus.ENABLED
        ).first()
        if not data_source:
            raise error_codes.DATA_SOURCE_NOT_ENABLED

        # 数据源用户即使被停用，也是允许被设置为其他人的 Leader 滴
        queryset = DataSourceUser.objects.filter(data_source=data_source)
        if keyword := data.get("keyword"):
            queryset = queryset.filter(Q(username__icontains=keyword) | Q(full_name__icontains=keyword))

        return queryset

    @swagger_auto_schema(
        tags=["data_source_organization"],
        operation_description="数据源用户上级列表",
        query_serializer=LeaderSearchInputSLZ(),
        responses={status.HTTP_200_OK: LeaderSearchOutputSLZ(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class DataSourceDepartmentsListApi(CurrentUserTenantMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated, perm_class(PermAction.MANAGE_TENANT)]
    serializer_class = DepartmentSearchOutputSLZ

    def get_queryset(self):
        slz = DepartmentSearchInputSLZ(data=self.request.query_params)
        slz.is_valid(raise_exception=True)
        data = slz.validated_data

        # 校验数据源是否存在
        data_source = DataSource.objects.filter(
            owner_tenant_id=self.get_current_tenant_id(), id=self.kwargs["id"], status=DataSourceStatus.ENABLED
        ).first()
        if not data_source:
            raise error_codes.DATA_SOURCE_NOT_ENABLED

        queryset = DataSourceDepartment.objects.filter(
            data_source=data_source, status=DataSourceDepartmentStatus.ENABLED
        )
        if name := data.get("name"):
            queryset = queryset.filter(name__icontains=name)

        return queryset

    @swagger_auto_schema(
        tags=["data_source_organization"],
        operation_description="数据源部门列表",
        query_serializer=DepartmentSearchInputSLZ(),
        responses={status.HTTP_200_OK: DepartmentSearchOutputSLZ(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class DataSourceUserRetrieveUpdateDestroyApi(
    CurrentUserTenantMixin, ExcludePatchAPIViewMixin, generics.RetrieveUpdateDestroyAPIView
):
    queryset = DataSourceUser.objects.all()
    lookup_url_kwarg = "id"
    permission_classes = [IsAuthenticated, perm_class(PermAction.MANAGE_TENANT)]
    serializer_class = UserRetrieveOutputSLZ

    @swagger_auto_schema(
        tags=["data_source_organization"],
        operation_description="数据源用户详情",
        responses={status.HTTP_200_OK: UserRetrieveOutputSLZ()},
    )
    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=["data_source_organization"],
        operation_description="更新数据源用户",
        request_body=UserUpdateInputSLZ(),
        responses={status.HTTP_204_NO_CONTENT: ""},
    )
    def put(self, request, *args, **kwargs):
        user = self.get_object()
        if not user.data_source.is_local:
            raise error_codes.DATA_SOURCE_USER_UPDATE_FAILED

        slz = UserUpdateInputSLZ(
            data=request.data,
            context={
                "data_source_id": user.data_source_id,
                "data_source_user_id": user.id,
                "tenant_id": self.get_current_tenant_id(),
            },
        )
        slz.is_valid(raise_exception=True)
        data = slz.validated_data

        # 用户数据整合
        user_info = DataSourceUserEditableInfo(
            full_name=data["full_name"],
            email=data["email"],
            phone_country_code=data["phone_country_code"],
            phone=data["phone"],
            logo=data["logo"],
            extras=data["extras"],
        )
        relation_info = DataSourceUserRelationInfo(
            department_ids=data["department_ids"], leader_ids=data["leader_ids"]
        )
        DataSourceUserHandler.update_user(user, user_info, relation_info)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @swagger_auto_schema(
        tags=["data_source_organization"],
        operation_description="删除数据源用户",
        responses={status.HTTP_204_NO_CONTENT: ""},
    )
    def delete(self, request, *args, **kwargs):
        data_source_user = self.get_object()
        if data_source_user.status != DataSourceUserStatus.DISABLED:
            raise error_codes.DATA_SOURCE_USER_DELETE_FAILED.f("仅可删除已停用的数据源用户")

        if not data_source_user.data_source.is_local:
            raise error_codes.DATA_SOURCE_USER_DELETE_FAILED.f("仅可删除本地数据源用户")

        data_source_user.status = DataSourceUserStatus.DELETED
        data_source_user.updater = request.user.username
        data_source_user.save(update_fields=["status", "updater", "updated_at"])

        # 关联的租户用户也一并标记为软删除
        TenantUser.objects.filter(data_source_user=data_source_user).update(
            status=TenantUserStatus.DELETED, updater=request.user.username, updated_at=timezone.now()
        )


class DataSourceUserSwitchStatusApi(ExcludePutAPIViewMixin, generics.UpdateAPIView):
    """切换数据源用户状态（启/停  ）"""

    queryset = DataSourceUser.objects.filter(status__in=[DataSourceUserStatus.ENABLED, DataSourceUserStatus.DISABLED])
    lookup_url_kwarg = "id"
    permission_classes = [IsAuthenticated, perm_class(PermAction.MANAGE_TENANT)]
    serializer_class = DataSourceUserSwitchStatusOutputSLZ

    @swagger_auto_schema(
        tags=["data_source_organization"],
        operation_description="变更数据源用户状态",
        responses={status.HTTP_200_OK: DataSourceUserSwitchStatusOutputSLZ()},
    )
    def patch(self, request, *args, **kwargs):
        user = self.get_object()
        user.status = (
            DataSourceUserStatus.DISABLED
            if user.status == DataSourceUserStatus.ENABLED
            else DataSourceUserStatus.ENABLED
        )
        user.updater = request.user.username
        user.save(update_fields=["status", "updater", "updated_at"])

        # 停用数据源用户会导致其关联的租户用户被停用，但是启用则不会影响，需要到租户用户侧手动启用
        if user.status == DataSourceUserStatus.DISABLED:
            self._disable_related_tenant_users(user, request.user.username)

        return Response(DataSourceUserSwitchStatusOutputSLZ(instance={"status": user.status.value}).data)

    def _disable_related_tenant_users(self, data_source_user: DataSourceUser, operator: str):
        """停用与被停用的数据源用户关联的租户用户"""
        TenantUser.objects.filter(data_source_user=data_source_user).update(
            status=TenantUserStatus.DISABLED, updator=operator, updated_at=timezone.now()
        )


class DataSourceUserPasswordResetApi(ExcludePatchAPIViewMixin, generics.UpdateAPIView):
    queryset = DataSourceUser.objects.filter(status=DataSourceUserStatus.ENABLED)
    lookup_url_kwarg = "id"
    permission_classes = [IsAuthenticated, perm_class(PermAction.MANAGE_TENANT)]

    @swagger_auto_schema(
        tags=["data_source_organization"],
        operation_description="重置数据源用户密码",
        request_body=DataSourceUserPasswordResetInputSLZ(),
        responses={status.HTTP_204_NO_CONTENT: ""},
    )
    def put(self, request, *args, **kwargs):
        user = self.get_object()
        data_source = user.data_source
        plugin_config = data_source.get_plugin_cfg()

        if not (data_source.is_local and plugin_config.enable_account_password_login):
            raise error_codes.DATA_SOURCE_OPERATION_UNSUPPORTED.f(
                _("仅可以重置 已经启用账密登录功能 的 本地数据源 的用户密码")
            )

        slz = DataSourceUserPasswordResetInputSLZ(
            data=request.data,
            context={
                "plugin_config": plugin_config,
                "data_source_user_id": user.id,
            },
        )
        slz.is_valid(raise_exception=True)
        raw_password = slz.validated_data["password"]

        DataSourceUserHandler.update_password(
            data_source_user=user,
            password=raw_password,
            valid_days=plugin_config.password_rule.valid_time,
            operator=request.user.username,
        )

        # 发送新密码通知到用户
        send_reset_password_to_user.delay(user.id, raw_password)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DataSourceUserOrganizationPathListApi(generics.ListAPIView):
    queryset = DataSourceUser.objects.all()
    lookup_url_kwarg = "id"
    permission_classes = [IsAuthenticated, perm_class(PermAction.MANAGE_TENANT)]

    @swagger_auto_schema(
        tags=["data_source_organization"],
        operation_description="数据源用户所属部门的部门路径",
        responses={status.HTTP_200_OK: DataSourceUserOrganizationPathOutputSLZ()},
    )
    def get(self, request, *args, **kwargs):
        data_source_user = self.get_object()

        dept_ids = DataSourceDepartmentUserRelation.objects.filter(
            user_id=data_source_user.id,
        ).values_list("department_id", flat=True)

        if not dept_ids:
            return Response()

        organization_paths: List[str] = []
        # NOTE: 用户部门数量不会很多，且该 API 调用不频繁，这里的 N+1 问题可以先不处理?
        for dept_relation in DataSourceDepartmentRelation.objects.filter(department_id__in=dept_ids):
            dept_names = list(
                dept_relation.get_ancestors(include_self=True).values_list("department__name", flat=True)
            )
            organization_paths.append("/".join(dept_names))

        return Response(DataSourceUserOrganizationPathOutputSLZ({"organization_paths": organization_paths}).data)


class DataSourceDepartmentSwitchStatusApi(ExcludePutAPIViewMixin, generics.UpdateAPIView):
    """切换数据源部门状态（启/停）"""

    queryset = DataSourceDepartment.objects.filter(
        status__in=[DataSourceUserStatus.ENABLED, DataSourceUserStatus.DISABLED]
    )
    lookup_url_kwarg = "id"
    permission_classes = [IsAuthenticated, perm_class(PermAction.MANAGE_TENANT)]
    serializer_class = DataSourceDepartmentSwitchStatusOutputSLZ

    @swagger_auto_schema(
        tags=["data_source_organization"],
        operation_description="变更数据源部门状态",
        responses={status.HTTP_200_OK: DataSourceDepartmentSwitchStatusOutputSLZ()},
    )
    def patch(self, request, *args, **kwargs):
        dept = self.get_object()
        dept.status = (
            DataSourceDepartmentStatus.DISABLED
            if dept.status == DataSourceDepartmentStatus.ENABLED
            else DataSourceDepartmentStatus.ENABLED
        )
        dept.updater = request.user.username
        dept.save(update_fields=["status", "updater", "updated_at"])

        # 停用数据源部门会导致其子孙部门 + 关联的租户部门被停用
        # 但是启用时候只能恢复子孙部门，对租户部门侧没有影响（需要手动到租户侧启用）
        self._update_descendants_data_source_depts_status(dept, request.user.username)
        if dept.status == DataSourceDepartmentStatus.DISABLED:
            self._disable_related_tenant_depts(dept, request.user.username)

        return Response(DataSourceDepartmentSwitchStatusOutputSLZ(instance={"status": dept.status.value}).data)

    def _update_descendants_data_source_depts_status(self, data_source_dept: DataSourceDepartment, operator: str):
        """批量更新子孙部门的状态，保持与父部门一致"""
        dept_rel = DataSourceDepartmentRelation.objects.filter(department=data_source_dept).first()
        # 没有子孙部门，直接返回
        if not dept_rel:
            return

        dept_ids = dept_rel.get_descendants().values_list("department_id", flat=True)
        DataSourceDepartment.objects.filter(id__in=dept_ids).update(
            status=data_source_dept.status, updater=operator, updated_at=timezone.now()
        )

    def _disable_related_tenant_depts(self, data_source_dept: DataSourceDepartment, operator: str):
        """停用与被停用的数据源用户关联的租户用户"""
        dept_ids = [data_source_dept.id]
        if dept_rel := DataSourceDepartmentRelation.objects.filter(department=data_source_dept).first():
            dept_ids = dept_rel.get_descendants(include_self=True).values_list("department_id", flat=True)

        TenantDepartment.objects.filter(data_source_department_id__in=dept_ids).update(
            status=TenantDepartmentStatus.DISABLED, updator=operator, updated_at=timezone.now()
        )
