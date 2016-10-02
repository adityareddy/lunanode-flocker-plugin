# Copyright (c) 2015 Huawei Technologies Co., Ltd.
# See LICENSE file for details.

"""
Functional tests for HuaweiBlockDeviceAPI.
"""

from uuid import uuid4
from bitmath import Byte, GiB
from flocker.node.agents.test.test_blockdevice import (
    make_iblockdeviceapi_tests
)
from flocker.testtools import skip_except

from huawei_oceanstor_flocker_plugin.huawei_oceanstor_blockdevice import (
    HuaweiBlockDeviceAPI
)
from huawei_oceanstor_flocker_plugin import constants

global_test_api = HuaweiBlockDeviceAPI(
                  cluster_id=unicode(uuid4()),
                  huawei_conf_file=constants.HUAWEI_CONFIG_FILE,
                  compute_instance_id=None,
                  allocation_unit=None)


def detach_destroy_volumes(api):
    """
    Detach and destroy all volumes known to this API.
    :param : api object
    """
    volumes = api.list_volumes()

    for volume in volumes:
        if volume.attached_to is not None:
            api.detach_volume(volume.blockdevice_id)
        api.destroy_volume(volume.blockdevice_id)


def get_hwblockdeviceapi_with_cleanup(test_case, api):
    """
    Return a ``HuaweiBlockDeviceAPI`and register a ``test_case``
    cleanup callback to remove any volumes that are created during each test.
    :param test_case object
    """
    test_case.addCleanup(detach_destroy_volumes, api)

    return api


def huaweiblockdeviceapi_for_test(test_case, api):
    """
    Create a ``HuaweiBlockDeviceAPI`` instance for use in tests.
    :returns: A ``HuaweiBlockDeviceAPI`` instance
    """
    return get_hwblockdeviceapi_with_cleanup(test_case, api)


@skip_except(
    supported_tests=[
        'test_interface',
        'test_list_volume_empty',
        'test_listed_volume_attributes',
        'test_created_is_listed',
        'test_created_volume_attributes',
        'test_destroy_unknown_volume',
        'test_destroy_volume',
        'test_destroy_destroyed_volume',
        'test_attach_unknown_volume',
        'test_attach_attached_volume',
        'test_attach_elsewhere_attached_volume',
        'test_attach_unattached_volume',
        'test_attached_volume_listed',
        'test_attach_volume_validate_size',
        'test_multiple_volumes_attached_to_host',
        'test_detach_unknown_volume',
        'test_detach_detached_volume',
        'test_reattach_detached_volume',
        'test_attach_destroyed_volume',
        'test_list_attached_and_unattached',
        'test_compute_instance_id_nonempty',
        'test_compute_instance_id_unicode',
        'test_resize_volume_listed',
        'test_resize_unknown_volume',
        'test_resize_destroyed_volume',
        'test_get_device_path_device',
        'test_get_device_path_unknown_volume',
        'test_get_device_path_unattached_volume',
        'test_detach_volume',
        'test_get_device_path_device_repeatable_results',
        'test_device_size'
    ]
)
class HuaweiBlockDeviceAPIInterfaceTests(
        make_iblockdeviceapi_tests(
            blockdevice_api_factory=(
                lambda test_case: huaweiblockdeviceapi_for_test(
                    test_case=test_case, api=global_test_api
                )
            ),
            minimum_allocatable_size=int(GiB(1).to_Byte().value),
            device_allocation_unit=int(GiB(1).to_Byte().value),
            unknown_blockdevice_id_factory=lambda test: u"vol-00000000",
        )
):

    """
    Interface adherence Tests for ``HuaweiBlockDeviceAPI``
    """
