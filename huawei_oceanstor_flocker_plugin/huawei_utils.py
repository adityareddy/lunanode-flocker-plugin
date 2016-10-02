# Copyright (c) 2015 Huawei Technologies Co., Ltd.
# See LICENSE file for details.

import base64
from uuid import uuid4, UUID
from huawei_oceanstor_flocker_plugin.log import LOG
import os
import re
import six
from xml.etree import ElementTree as ET
from subprocess import check_output


def get_login_info(xml_file_path):
    """Get login IP, user name and password from config file."""
    login_info = {}
    tree = ET.parse(xml_file_path)
    root = tree.getroot()
    login_info['RestURL'] = root.findtext('Storage/RestURL').strip()

    for key in ['UserName', 'UserPassword']:
        node = root.find('Storage/%s' % key)
        node_text = node.text
        login_info[key] = node_text

    return login_info


def compute_new_instance_id():
    id = uuid4()
    id = base64.encodestring(str(id.bytes))
    id = id.rstrip('=\n').replace('/', '_').replace('+', '-')
    return id


def get_instance_id(xml_file_path):
    tree = ET.parse(xml_file_path)
    root = tree.getroot()
    instance_id = root.findtext('Instance/ID')
    if instance_id is None:
        instance_id = compute_new_instance_id()
        instanceE = ET.SubElement(root, 'Instance')
        idE = ET.SubElement(instanceE, 'ID')
        idE.text = instance_id
        tree.write(xml_file_path, 'UTF-8')
    return instance_id


def encode_name(dataset_id, cluster_id):
    uuid_encoded = base64.encodestring(str(dataset_id.bytes))
    LOG.info("uuid_encoded=%s" % uuid_encoded)

    uuid_encoded = uuid_encoded.rstrip('=\n').replace('/', '_')
    uuid_encoded = uuid_encoded.replace('+', '-')
    name = 'f%s%s' % (uuid_encoded, str(cluster_id)[:8])
    LOG.info("uuid_encoded=%s, name=%s" % (uuid_encoded, name))
    return name


def decode_name(volume_name, cluster_id):
    uuid_encoded = str((volume_name[1:23]) + '==').replace('_', '/')
    uuid_encoded = uuid_encoded.replace('-', '+')
    LOG.info("volume_name=%s, uuid_encoded=%s" % (volume_name, uuid_encoded))
    dataset_id = UUID(bytes=(base64.decodestring(uuid_encoded)))
    LOG.info("decoded dataset_id=%s" % dataset_id)
    return dataset_id


def is_cluster_volume(volume_name, cluster_id):
    if volume_name.startswith("f") and len(volume_name) > 24:
        tmp_cluster_id = volume_name[23:]
        if tmp_cluster_id is not None:
            if tmp_cluster_id in str(cluster_id):
                return True
    return False


def iscsi_get_initiator():
    initiator_file = "/etc/iscsi/initiatorname.iscsi"
    iscsin = os.popen('cat %s' % initiator_file).read()
    match = re.search('InitiatorName=.*', iscsin)
    if len(match.group(0)) > 13:
        initiator = match.group(0)[14:]
        LOG.info("get iscsi initiator=%s" % initiator)
        return initiator
    LOG.error("can't find iscsi initiator")
    return None


def parse_xml_file(xml_file_path):
    """Get root of xml file."""
    try:
        tree = ET.parse(xml_file_path)
        root = tree.getroot()
        return root
    except IOError as err:
        LOG.error('parse_xml_file: %s.' % err.message)
        raise


def get_iscsi_conf(xml_file_path):
    """Get iSCSI info from config file."""
    iscsiinfo = {}
    root = parse_xml_file(xml_file_path)
    target_ip = root.findtext('iSCSI/DefaultTargetIP').strip()
    iscsiinfo['DefaultTargetIP'] = target_ip
    initiator_list = []

    for dic in root.findall('iSCSI/Initiator'):
        # Strip values of dict.
        tmp_dic = {}
        for k in dic.items():
            tmp_dic[k[0]] = k[1].strip()

        initiator_list.append(tmp_dic)

    iscsiinfo['Initiator'] = initiator_list

    return iscsiinfo


def get_protocol_info(filename):
    """Get connection protocol from config file."""
    root = parse_xml_file(filename)
    protocol = root.findtext('Storage/Protocol').strip()
    if protocol in ('iSCSI', 'FC'):
        return protocol
    else:
        LOG.error("Wrong protocol. Protocol should be set to either "
                  "iSCSI or FC.")
        return None


def rescan_scsi():
    hosts = check_output(["ls", "/sys/class/scsi_host/"])
    for host in hosts.split():
        host_scan = "/sys/class/scsi_host/"+host+"/scan"
        try:
            with open(host_scan, 'w') as f:
                f.write("- - -")
        except IOError as err:
            LOG.error("File error: %s." % six.text_type(err))


def remove_scsi_device(device):
    path = "/sys/block/%s/device/delete" % device.basename()
    try:
        with open(path, 'w') as f:
            f.write("1")
    except IOError as err:
        LOG.error("File error: %s." % six.text_type(err))


def get_fc_hbas():
    """Get the Fibre Channel HBA information."""
    out = check_output(['systool', '-c', 'fc_host', '-v'])
    if out is None:
        return []

    lines = out.split('\n')
    lines = lines[2:]
    hbas = []
    hba = {}
    lastline = None
    for line in lines:
        line = line.strip()
        if line == '' and lastline == '':
            if len(hba) > 0:
                hbas.append(hba)
                hba = {}
        else:
            val = line.split('=')
            if len(val) == 2:
                key = val[0].strip().replace(" ", "")
                value = val[1].strip()
                hba[key] = value.replace('"', '')
        lastline = line

    return hbas


def get_fc_wwpns():
    """Get Fibre Channel WWPNs from the system, if any."""
    hbas = get_fc_hbas()
    if not hbas:
        return []

    wwpns = []
    for hba in hbas:
        if hba['port_state'] == 'Online':
            wwpn = hba['port_name'].replace('0x', '')
            wwpns.append(wwpn)

    return wwpns


def get_all_block_device():
    output = check_output(["ls", "/sys/block"])
    LOG.info(output)
    return output.split()


def get_wwn_of_deviceblock(bd):
    try:
        output = check_output(
            ["/lib/udev/scsi_id", "--whitelisted", "--device=/dev/"+bd])
    except Exception as err:
        LOG.info("/lib/udev/scsi_id failed, error=%s" % err)
        return None
    LOG.info("bd=%s, wwn=%s" % (bd, output))
    return output


def get_pools(xml_file_path):
    """Get pools from huawei conf file."""
    root = parse_xml_file(xml_file_path)
    pool_names = root.findtext('LUN/StoragePool')
    if not pool_names:
        msg = ('Invalid resource pool name. '
               'Please check the config file.')
        LOG.error(msg)
        return None
    return pool_names


def get_lun_conf_params(xml_file_path):
    """Get parameters from config file for creating lun."""
    lunsetinfo = {
        'LUNType': 0,
        'StripUnitSize': '64',
        'WriteType': '1',
        'MirrorSwitch': '1',
        'PrefetchType': '3',
        'PrefetchValue': '0',
        'PrefetchTimes': '0',
        'policy': '0',
        'readcachepolicy': '2',
        'writecachepolicy': '5',
    }
    # Default lun set information.
    root = parse_xml_file(xml_file_path)
    luntype = root.findtext('LUN/LUNType')
    if luntype:
        if luntype.strip() in ['Thick', 'Thin']:
            lunsetinfo['LUNType'] = luntype.strip()
            if luntype.strip() == 'Thick':
                lunsetinfo['LUNType'] = 0
            elif luntype.strip() == 'Thin':
                lunsetinfo['LUNType'] = 1

        else:
            err_msg = ((
                "LUNType config is wrong. LUNType must be 'Thin'"
                " or 'Thick'. LUNType: %(luntype)s.")
                % {'luntype': luntype})
            LOG.error(err_msg)
            return None
    else:
        lunsetinfo['LUNType'] = 0

    stripunitsize = root.findtext('LUN/StripUnitSize')
    if stripunitsize is not None:
        lunsetinfo['StripUnitSize'] = stripunitsize.strip()
    writetype = root.findtext('LUN/WriteType')
    if writetype is not None:
        lunsetinfo['WriteType'] = writetype.strip()
    mirrorswitch = root.findtext('LUN/MirrorSwitch')
    if mirrorswitch is not None:
        lunsetinfo['MirrorSwitch'] = mirrorswitch.strip()

    prefetch = root.find('LUN/Prefetch')
    if prefetch is not None and prefetch.attrib['Type']:
        fetchtype = prefetch.attrib['Type']
        if fetchtype in ['0', '1', '2', '3']:
            lunsetinfo['PrefetchType'] = fetchtype.strip()
            typevalue = prefetch.attrib['Value'].strip()
            if lunsetinfo['PrefetchType'] == '1':
                double_value = int(typevalue) * 2
                typevalue_double = six.text_type(double_value)
                lunsetinfo['PrefetchValue'] = typevalue_double
            elif lunsetinfo['PrefetchType'] == '2':
                lunsetinfo['PrefetchValue'] = typevalue
        else:
            err_msg = ((
                'PrefetchType config is wrong. PrefetchType'
                ' must be in 0,1,2,3. PrefetchType is: %(fetchtype)s.')
                % {'fetchtype': fetchtype})
            LOG.error(err_msg)
            return None
    else:
        LOG.info((
            'Use default PrefetchType. '
            'PrefetchType: Intelligent.'))

    return lunsetinfo
