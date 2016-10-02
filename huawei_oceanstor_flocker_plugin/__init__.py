# Copyright (c) 2015 Huawei Technologies Co., Ltd.
# See LICENSE file for details.

from flocker.node import BackendDescription, DeployerType
from huawei_oceanstor_flocker_plugin.huawei_oceanstor_blockdevice import (
    HuaweiBlockDeviceAPI
)


def api_factory(cluster_id, **kwargs):
    return HuaweiBlockDeviceAPI(cluster_id=cluster_id,
                                api_id=kwargs[u"api_id"],
                                api_key=kwargs[u"api_key"])

FLOCKER_BACKEND = BackendDescription(
    name=u"huawei_oceanstor_flocker_plugin",
    needs_reactor=False, needs_cluster_id=True,
    api_factory=api_factory, deployer_type=DeployerType.block)
