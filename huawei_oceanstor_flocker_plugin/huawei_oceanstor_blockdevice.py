# Copyright (c) 2015 Huawei Technologies Co., Ltd.
# See LICENSE file for details.

from flocker.node.agents.blockdevice import (
    VolumeException, AlreadyAttachedVolume,
    UnknownVolume, UnattachedVolume,
    IBlockDeviceAPI, BlockDeviceVolume
)

from uuid import uuid4, UUID
from zope.interface import implementer
from twisted.python.filepath import FilePath

from huawei_oceanstor_flocker_plugin import rest_client
from huawei_oceanstor_flocker_plugin import lndynamic
from huawei_oceanstor_flocker_plugin import huawei_utils
from huawei_oceanstor_flocker_plugin.log import LOG

import json
import math
import socket
import urllib2


@implementer(IBlockDeviceAPI)
class HuaweiBlockDeviceAPI(object):
    """
    Huawei driver implemented ``IBlockDeviceAPI``.
    """
    def __init__(self, cluster_id, api_id, api_key,
                 compute_instance_id=None,
                 allocation_unit=None):
        """
        :param cluster_id: An ID that include in the
            names of Huawei volumes to identify cluster.
        :param huawei_conf_file: The path of huawei config file.
        :param compute_instance_id: An ID that used to create
            host on the array to identify node.
        :param allocation_unit: Allocation unit on array.
        :returns: A ``BlockDeviceVolume``.
        """
        LOG.info("Huawei block device init")
        self.api = lndynamic.LNDynamic(api_id, api_key)
        LOG.info("Finish huawei block device init")

    def allocation_unit(self):
        """
        The size, in bytes up to which ``IDeployer`` will round volume
        sizes before calling ``IBlockDeviceAPI.create_volume``.

        :returns: ``int``
        """
        LOG.info("Call allocation_unit")
        return 1073741824

    def compute_instance_id(self):
        """
        Get an identifier for this node.

        This will be compared against ``BlockDeviceVolume.attached_to``
        to determine which volumes are locally attached and it will be used
        with ``attach_volume`` to locally attach volumes.

        :returns: A ``unicode`` object giving a provider-specific node
            identifier which identifies the node where the method is run.
        """

        LOG.info("Call compute_instance_id")
        list_vms = self.api.request('vm', 'list', {'region': 'toronto'})
        hostname = urllib2.urlopen("http://rancher-metadata/latest/self/host/hostname").read()
        for vm in list_vms['vms']:
            LOG.info("hostname=%s, gethostname=%s"% (vm['hostname'], hostname))
            if vm['hostname'] == hostname:
                LOG.info("vm_id=%s"% (unicode(vm['vm_id'])))
                return unicode(vm['vm_id'])
        return None

    def create_volume(self, dataset_id, size):
        """
        Create a new volume.

        When called by ``IDeployer``, the supplied size will be
        rounded up to the nearest ``IBlockDeviceAPI.allocation_unit()``

        :param UUID dataset_id: The Flocker dataset ID of the dataset on this
            volume.
        :param int size: The size of the new volume in bytes.
        :returns: A ``BlockDeviceVolume``.
        """
        LOG.info("Call create_volume, dataset_id=%s, size=%d"
                 % (dataset_id, size))
        result = self.api.request('volume', 'create', {'region': 'toronto', 'label':str(dataset_id), 'size': math.ceil(size/1073741824)})
        volume = BlockDeviceVolume(
            size=int(size),
            attached_to=None,
            dataset_id=dataset_id,
            blockdevice_id=unicode(result['volume_id'])
        )
        return volume

    def destroy_volume(self, blockdevice_id):
        """
        Destroy an existing volume.

        :param unicode blockdevice_id: The unique identifier for the volume to
            destroy.

        :raises UnknownVolume: If the supplied ``blockdevice_id`` does not
            exist.

        :return: ``None``
        """

        LOG.info("Call destroy_volume blockdevice_id=%s" % blockdevice_id)
        try:
            self.api.request('volume', 'delete', {'region': 'toronto', 'volume_id': blockdevice_id})
        except Exception:
            raise UnknownVolume(blockdevice_id)

    def attach_volume(self, blockdevice_id, attach_to):
        """
        Attach ``blockdevice_id`` to the node indicated by ``attach_to``.

        :param unicode blockdevice_id: The unique identifier for the block
            device being attached.
        :param unicode attach_to: An identifier like the one returned by the
            ``compute_instance_id`` method indicating the node to which to
            attach the volume.

        :raises UnknownVolume: If the supplied ``blockdevice_id`` does not
            exist.
        :raises AlreadyAttachedVolume: If the supplied ``blockdevice_id`` is
            already attached.

        :returns: A ``BlockDeviceVolume`` with a ``attached_to`` attribute set
            to ``attach_to``.
        """

        LOG.info("Call attach_volume blockdevice_id=%s, attach_to=%s"
                 % (blockdevice_id, attach_to))

        result = self.api.request('volume', 'info', {'region': 'toronto', 'volume_id': blockdevice_id})
        if result['success'] == 'no':
            raise UnknownVolume(blockdevice_id)

        if result['volume']['status'] == 'in-use':
            raise AlreadyAttachedVolume(blockdevice_id)

        result = self.api.request('volume', 'attach', {'region': 'toronto', 'volume_id': blockdevice_id, 'vm_id': attach_to, 'target': 'auto'})
        result = self.api.request('volume', 'info', {'region': 'toronto', 'volume_id': blockdevice_id})
        
        attached_volume = BlockDeviceVolume(
            size=int(result['volume']['size']),
            attached_to=unicode(attach_to),
            dataset_id=UUID(result['volume']['name']),
            blockdevice_id=unicode(blockdevice_id))
        return attached_volume

    def detach_volume(self, blockdevice_id):
        """
        Detach ``blockdevice_id`` from whatever host it is attached to.

        :param unicode blockdevice_id: The unique identifier for the block
            device being detached.

        :raises UnknownVolume: If the supplied ``blockdevice_id`` does not
            exist.
        :raises UnattachedVolume: If the supplied ``blockdevice_id`` is
            not attached to anything.
        :returns: ``None``
        """

        LOG.info("Call detach_volume blockdevice_id=%s" % blockdevice_id)
        result = self.api.request('volume', 'info', {'region': 'toronto', 'volume_id': blockdevice_id})
        if result['volume']['status'] == 'in-use':
            self.api.request('volume', 'detach', {'region': 'toronto', 'volume_id': blockdevice_id})
        else:
            LOG.error("Volume %s not attached." % blockdevice_id)
            raise UnattachedVolume(blockdevice_id)

    def get_attached_to(self, item):
        """
        """
        LOG.info("Call get_attached_to")
        result = self.api.request('volume', 'info', {'region': 'toronto', 'volume_id': item['id']})
        if result['volume']['attached']:
            return unicode(result['volume']['attached'])
        return None

    def list_volumes(self):
        """
        List all the block devices available via the back end API.

        :returns: A ``list`` of ``BlockDeviceVolume``s.
        """
        LOG.info("Call list_volumes")
        volumes = []
        result = self.api.request('volume', 'list', {'region': 'toronto'})

        if 'volumes' in result:
            for item in result['volumes']:
                volume = BlockDeviceVolume(
                    size=int(item['size']),
                    attached_to=self.get_attached_to(item),
                    dataset_id=UUID(item['name']),
                    blockdevice_id=unicode(item['id'])
                )
                volumes.append(volume)
        return volumes

    def get_device_path(self, blockdevice_id):
        """
        Return the device path that has been allocated to the block device on
        the host to which it is currently attached.

        :param unicode blockdevice_id: The unique identifier for the block
            device.
        :raises UnknownVolume: If the supplied ``blockdevice_id`` does not
            exist.
        :raises UnattachedVolume: If the supplied ``blockdevice_id`` is
            not attached to a host.
        :returns: A ``FilePath`` for the device.
        """

        LOG.info("Call get_device_path")

        result = self.api.request('volume', 'info', {'region': 'toronto', 'volume_id': blockdevice_id})
        if result['success'] == 'no':
            raise UnknownVolume(blockdevice_id)

        if result['volume']['status'] != 'in-use':
            raise UnattachedVolume(blockdevice_id)

        list_volumes = self.api.request('volume', 'list', {'region': 'toronto'})
        volume_suffix_list = 'cdefghijklmnopqrstuv'
        for item in list_volumes['volumes']:
            if unicode(item['id']) == blockdevice_id:
                LOG.info("device_path found: %s" % volume_suffix_list[list_volumes['volumes'].index(item)])
                return FilePath("/dev/vd" + volume_suffix_list[list_volumes['volumes'].index(item)])

        return None
