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
import logging

from django.db.models import Q
from django.utils import timezone

from bkuser.apps.tenant.constants import TenantUserStatus
from bkuser.apps.tenant.models import Tenant, TenantUser
from bkuser.celery import app
from bkuser.common.task import BaseTask

logger = logging.getLogger(__name__)


@app.task(base=BaseTask, ignore_result=True)
def expire_tenant_users(tenant_id: str):
    """对过期的租户用户修改状态为过期"""
    logger.info("[celery] receive task: expire_tenant_users, tenant_id is %s", tenant_id)

    # Q：为什么不使用 timezone.now 而是要转换成 midnight?
    # A: 相关讨论：https://github.com/TencentBlueKing/bk-user/pull/1504#discussion_r1438059142
    midnight = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    # 状态优先级：软删除 > 停用 > 过期 > 正常，即过期状态只能覆盖正常状态，无法覆盖软删除 / 停用
    # 否则会出现这种场景：用户状态软删除，上一个状态停用，覆盖停用，软删除恢复后，状态变成过期的
    tenant_users = TenantUser.objects.filter(
        tenant_id=tenant_id,
        account_expired_at__lte=midnight,
    ).filter(
        Q(status=TenantUserStatus.ENABLED)
        | Q(
            status__in=[TenantUserStatus.DISABLED, TenantUserStatus.DELETED],
            previous_status=TenantUserStatus.ENABLED,
        )
    )

    if not tenant_users.exists():
        logger.info("tenant %s not tenant user need set expired status, skip...", tenant_id)
        return

    logger.info("tenant %s set %d users as expired status...", tenant_id, tenant_users.count())
    # 对于状态为正常的租户用户，修改状态为过期，上一个状态为正常
    tenant_users.filter(status=TenantUserStatus.ENABLED).update(
        status=TenantUserStatus.EXPIRED, previous_status=TenantUserStatus.ENABLED, updated_at=timezone.now()
    )
    # 修改状态为已停用 / 软删除的租户用户的 上一个状态为过期，为的是恢复 / 启用时候可用
    tenant_users.filter(status__in=[TenantUserStatus.DISABLED, TenantUserStatus.DELETED]).update(
        previous_status=TenantUserStatus.EXPIRED, updated_at=timezone.now()
    )


@app.task(base=BaseTask, ignore_result=True)
def build_and_run_expire_tenant_users_task():
    """构建并运行过期通知任务"""
    logger.info("[celery] receive period task: build_and_run_expire_tenant_users_task")

    for tenant_id in Tenant.objects.all().values_list("id", flat=True):
        expire_tenant_users.delay(tenant_id)
