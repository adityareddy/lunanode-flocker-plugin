# Copyright (c) 2015 Huawei Technologies Co., Ltd.
# See LICENSE file for details.

import cookielib
import json
import urllib2

from huawei_oceanstor_flocker_plugin import constants
from huawei_oceanstor_flocker_plugin.log import LOG
from huawei_oceanstor_flocker_plugin import huawei_utils


class VolumeBackendAPIException(Exception):
    """
    Exception from backed server
    """


class RestClient(object):
    """Common class for Huawei OceanStor storage system."""

    def __init__(self, configuration):
        self.configuration = configuration
        self.url = None
        self.device_id = None
        self._init_http_head()

    def _init_http_head(self):
        self.cookie = cookielib.CookieJar()
        self.headers = {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
        }

    def do_call(self, url=False, data=None, method=None,
                calltimeout=constants.SOCKET_TIMEOUT):
        """Send requests to server.

        Send HTTPS call, get response in JSON.
        Convert response into Python Object and return it.
        """
        if self.url:
            url = self.url + url

        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cookie))
        urllib2.install_opener(opener)
        res_json = None

        LOG.info(('\n\n\n\nRequest URL: %(url)s\n\n'
                   'Call Method: %(method)s\n\n'
                   'Request Data: %(data)s\n\n') % {'url': url,
                                                    'method': method,
                                                    'data': data})

        try:
            urllib2.socket.setdefaulttimeout(calltimeout)
            req = urllib2.Request(url, data, self.headers)
            if method:
                req.get_method = lambda: method
            res = urllib2.urlopen(req).read().decode("utf-8")

            if "xx/sessions" not in url:
                LOG.info(('\n\n\n\nRequest URL: %(url)s\n\n'
                           'Call Method: %(method)s\n\n'
                           'Request Data: %(data)s\n\n'
                           'Response Data:%(res)s\n\n')
                          % {'url': url, 'method': method,
                             'data': data, 'res': res})

        except Exception as err:
            LOG.error('Bad response from server: %(url)s.Error: %(err)s'
                      % {'url': url, 'err': err})
            json_msg = ('{"error":{"code": %s,"description": "Connect to '
                        'server error."}}') % constants.ERROR_CONNECT_TO_SERVER
            res_json = json.loads(json_msg)
            return res_json

        try:
            res_json = json.loads(res)
        except Exception as err:
            LOG.error('JSON transfer error: %s.' % err.message)
            raise

        return res_json

    def login(self):
        """Login array."""
        login_info = self.configuration
        urlstr = login_info['RestURL']
        url = urlstr + "xx/sessions"
        data = json.dumps({"username": login_info['UserName'],
                           "password": login_info['UserPassword'],
                           "scope": "0"})
        self._init_http_head()
        result = self.do_call(url, data,
                              calltimeout=constants.LOGIN_SOCKET_TIMEOUT)

        if (result['error']['code'] != 0) or ("data" not in result):
            LOG.error("Login error, reason is: %s." % result)
            return None

        LOG.info('Login success: %(url)s' % {'url': urlstr})
        self.device_id = result['data']['deviceid']
        self.url = urlstr + self.device_id
        self.headers['iBaseToken'] = result['data']['iBaseToken']

        return self.device_id

    def logout(self):
        """Logout the session."""
        url = "/sessions"
        if self.url:
            result = self.call(url, None, "DELETE")
            self._assert_rest_result(result, 'Logout session error.')

    def _assert_rest_result(self, result, err_str):
        if result['error']['code'] != 0:
            msg = ('%(err)s\nresult: %(res)s.'
                   % {'err': err_str, 'res': result})
            LOG.error(msg)
            raise VolumeBackendAPIException

    def _assert_data_in_result(self, result, msg):
        if 'data' not in result:
            err_msg = ('%s "data" was not in result.' % msg)
            LOG.error(err_msg)
            raise VolumeBackendAPIException

    def call(self, url, data=None, method=None):
        """Send requests to server.

        If fail, try another RestURL.
        """
        result = self.do_call(url, data, method)
        return result

    def _get_id_from_result(self, result, name, key):
        if 'data' in result:
            for item in result['data']:
                if name == item[key]:
                    return item['ID']

    def find_host(self, host_name):
        """Get the given host ID."""
        url = "/host?range=[0-65535]"
        result = self.call(url, None, "GET")
        self._assert_rest_result(result, ('Find host in hostgroup error.'))

        return self._get_id_from_result(result, host_name, 'NAME')

    def _add_host(self, hostname, host_name_before_hash):
        """Add a new host."""
        url = "/host"
        data = json.dumps({"TYPE": "21",
                           "NAME": hostname,
                           "OPERATIONSYSTEM": "0",
                           "DESCRIPTION": host_name_before_hash})
        result = self.call(url, data)
        self._assert_rest_result(result, 'Add new host error.')

        if 'data' in result:
            return result['data']['ID']

    def add_host_with_check(self, host_name):
        host_name_before_hash = None
        if host_name and (len(host_name) > constants.MAX_HOSTNAME_LENGTH):
            host_name_before_hash = host_name
            host_name = hash(host_name)

        host_id = self.find_host(host_name)
        if host_id:
            LOG.info((
                'add_host_with_check. '
                'host name: %(name)s, '
                'host id: %(id)s') %
                {'name': host_name,
                 'id': host_id})
            return host_id

        try:
            host_id = self._add_host(host_name, host_name_before_hash)
        except Exception:
            LOG.info((
                'Failed to create host: %(name)s. '
                'Check if it exists on the array.') %
                {'name': host_name})
            host_id = self.find_host(host_name)
            if not host_id:
                err_msg = ((
                    'Failed to create host: %(name)s. '
                    'Please check if it exists on the array.') %
                    {'name': host_name})
                LOG.error(err_msg)
                raise VolumeBackendAPIException

        LOG.info((
            'add_host_with_check. '
            'create host success. '
            'host name: %(name)s, '
            'host id: %(id)s') %
            {'name': host_name,
             'id': host_id})
        return host_id

    def _initiator_is_added_to_array(self, ininame):
        """Check whether the initiator is already added on the array."""
        url = "/iscsi_initiator?range=[0-256]"
        result = self.call(url, None, "GET")

        if self._get_id_from_result(result, ininame, 'ID'):
            return True
        return False

    def _add_initiator_to_array(self, initiator_name):
        """Add a new initiator to storage device."""
        url = "/iscsi_initiator"
        data = json.dumps({"TYPE": "222",
                           "ID": initiator_name,
                           "USECHAP": "false"})
        result = self.call(url, data, "POST")

    def is_initiator_associated_to_host(self, ininame):
        """Check whether the initiator is associated to the host."""
        url = "/iscsi_initiator?range=[0-256]"
        result = self.call(url, None, "GET")

        if 'data' in result:
            for item in result['data']:
                if item['ID'] == ininame and item['ISFREE'] == "true":
                    return False
        return True

    def find_chap_info(self, iscsi_conf, initiator_name):
        """Find CHAP info from xml."""
        chapinfo = None
        for ini in iscsi_conf['Initiator']:
            if ini['Name'] == initiator_name:
                if 'CHAPinfo' in ini:
                    chapinfo = ini['CHAPinfo']
                    break

        return chapinfo

    def _find_alua_info(self, iscsi_conf, initiator_name):
        """Find ALUA info from xml."""
        multipath_type = 0
        for ini in iscsi_conf['Initiator']:
            if ini['Name'] == initiator_name:
                if 'ALUA' in ini:
                    if ini['ALUA'] != '1' and ini['ALUA'] != '0':
                        msg = ('Invalid ALUA value.'
                               'ALUA value must be 1 or 0.')
                        LOG.error(msg)
                        raise VolumeBackendAPIException
                    else:
                        multipath_type = ini['ALUA']
                        break
        return multipath_type

    def _use_chap(self, chapinfo, initiator_name, host_id):
        """Use CHAP when adding initiator to host."""
        (chap_username, chap_password) = chapinfo.split(";")

        url = "/iscsi_initiator/" + initiator_name
        data = json.dumps({"TYPE": "222",
                           "USECHAP": "true",
                           "CHAPNAME": chap_username,
                           "CHAPPASSWORD": chap_password,
                           "ID": initiator_name,
                           "PARENTTYPE": "21",
                           "PARENTID": host_id})
        result = self.call(url, data, "PUT")
        msg = ('Use CHAP to associate initiator to host error. '
                  'Please check the CHAP username and password.')
        self._assert_rest_result(result, msg)

    def _add_initiator_to_host(self, initiator_name, host_id):
        url = "/iscsi_initiator/" + initiator_name
        data = json.dumps({"TYPE": "222",
                           "ID": initiator_name,
                           "USECHAP": "false",
                           "PARENTTYPE": "21",
                           "PARENTID": host_id})
        result = self.call(url, data, "PUT")
        self._assert_rest_result(result,
                                 'Associate initiator to host error.')

    def _use_alua(self, initiator_name, multipath_type):
        """Use ALUA when adding initiator to host."""
        url = "/iscsi_initiator"
        data = json.dumps({"ID": initiator_name,
                           "MULTIPATHTYPE": multipath_type})
        result = self.call(url, data, "PUT")

        self._assert_rest_result(
            result, 'Use ALUA to associate initiator to host error.')

    def _associate_initiator_to_host(self,
                                     xml_file_path,
                                     initiator_name,
                                     host_id):
        """Associate initiator with the host."""
        iscsi_conf = huawei_utils.get_iscsi_conf(xml_file_path)

        chapinfo = self.find_chap_info(iscsi_conf,
                                       initiator_name)
        multipath_type = self._find_alua_info(iscsi_conf,
                                              initiator_name)
        if chapinfo:
            LOG.info('Use CHAP when adding initiator to host.')
            self._use_chap(chapinfo, initiator_name, host_id)
        else:
            self._add_initiator_to_host(initiator_name, host_id)

        if multipath_type:
            LOG.info('Use ALUA when adding initiator to host.')
            self._use_alua(initiator_name, multipath_type)

    def ensure_initiator_added(self, xml_file_path, initiator_name, host_id):
        added = self._initiator_is_added_to_array(initiator_name)
        if not added:
            self._add_initiator_to_array(initiator_name)
        if not self.is_initiator_associated_to_host(initiator_name):
            self._associate_initiator_to_host(xml_file_path,
                                              initiator_name,
                                              host_id)

    def find_hostgroup(self, groupname):
        """Get the given hostgroup id."""
        url = "/hostgroup?range=[0-8191]"
        result = self.call(url, None, "GET")
        self._assert_rest_result(result, 'Get hostgroup information error.')

        return self._get_id_from_result(result, groupname, 'NAME')

    def _create_hostgroup(self, hostgroup_name):
        url = "/hostgroup"
        data = json.dumps({"TYPE": "14", "NAME": hostgroup_name})
        result = self.call(url, data)

        msg = 'Create hostgroup error.'
        self._assert_rest_result(result, msg)
        self._assert_data_in_result(result, msg)

        return result['data']['ID']

    def create_hostgroup_with_check(self, hostgroup_name):
        """Check if host exists on the array, or create it."""
        hostgroup_id = self.find_hostgroup(hostgroup_name)
        if hostgroup_id:
            LOG.info((
                'create_hostgroup_with_check. '
                'hostgroup name: %(name)s, '
                'hostgroup id: %(id)s') %
                {'name': hostgroup_name,
                 'id': hostgroup_id})
            return hostgroup_id

        try:
            hostgroup_id = self._create_hostgroup(hostgroup_name)
        except Exception:
            LOG.info((
                'Failed to create hostgroup: %(name)s. '
                'Please check if it exists on the array.') %
                {'name': hostgroup_name})
            hostgroup_id = self.find_hostgroup(hostgroup_name)
            if hostgroup_id is None:
                err_msg = ((
                    'Failed to create hostgroup: %(name)s. '
                    'Check if it exists on the array.')
                    % {'name': hostgroup_name})
                LOG.error(err_msg)
                raise VolumeBackendAPIException

        LOG.info((
            'create_hostgroup_with_check. '
            'Create hostgroup success. '
            'hostgroup name: %(name)s, '
            'hostgroup id: %(id)s') %
            {'name': hostgroup_name,
             'id': hostgroup_id})
        return hostgroup_id

    def _is_host_associate_to_hostgroup(self, hostgroup_id, host_id):
        """Check whether the host is associated to the hostgroup."""
        url_subfix = ("/host/associate?TYPE=21&"
                      "ASSOCIATEOBJTYPE=14&ASSOCIATEOBJID=%s" % hostgroup_id)

        url = url_subfix
        result = self.call(url, None, "GET")
        self._assert_rest_result(result, 'Check hostgroup associate error.')

        if self._get_id_from_result(result, host_id, 'ID'):
            return True

        return False

    def _associate_host_to_hostgroup(self, hostgroup_id, host_id):
        url = "/hostgroup/associate"
        data = json.dumps({"TYPE": "14",
                           "ID": hostgroup_id,
                           "ASSOCIATEOBJTYPE": "21",
                           "ASSOCIATEOBJID": host_id})

        result = self.call(url, data)
        self._assert_rest_result(result, ('Associate host to hostgroup '
                                 'error.'))

    def add_host_into_hostgroup(self, host_id):
        """Associate host to hostgroup.

        If hostgroup doesn't exist, create one.
        """
        hostgroup_name = constants.HOSTGROUP_PREFIX + host_id
        hostgroup_id = self.create_hostgroup_with_check(hostgroup_name)
        is_associated = self._is_host_associate_to_hostgroup(hostgroup_id,
                                                             host_id)
        if not is_associated:
            self._associate_host_to_hostgroup(hostgroup_id, host_id)

        return hostgroup_id

    def _find_lungroup(self, lungroup_name):
        """Get the given hostgroup id."""
        url = "/lungroup?range=[0-8191]"
        result = self.call(url, None, "GET")
        self._assert_rest_result(result, ('Get lungroup information error.'))

        return self._get_id_from_result(result, lungroup_name, 'NAME')

    def find_mapping_view(self, name):
        """Find mapping view."""
        url = "/mappingview?range=[0-8191]"
        result = self.call(url, None, "GET")

        msg = 'Find mapping view error.'
        self._assert_rest_result(result, msg)

        return self._get_id_from_result(result, name, 'NAME')

    def _create_lungroup(self, lungroup_name):
        url = "/lungroup"
        data = json.dumps({"DESCRIPTION": lungroup_name,
                           "APPTYPE": '0',
                           "GROUPTYPE": '0',
                           "NAME": lungroup_name})
        result = self.call(url, data)

        msg = 'Create lungroup error.'
        self._assert_rest_result(result, msg)
        self._assert_data_in_result(result, msg)

        return result['data']['ID']

    def _is_lun_associated_to_lungroup(self, lungroup_id, lun_id):
        """Check whether the lun is associated to the lungroup."""
        url_subfix = ("/lun/associate?TYPE=11&"
                      "ASSOCIATEOBJTYPE=256&ASSOCIATEOBJID=%s" % lungroup_id)

        url = url_subfix
        result = self.call(url, None, "GET")
        self._assert_rest_result(result, 'Check lungroup associate error.')

        if self._get_id_from_result(result, lun_id, 'ID'):
            return True

        return False

    def associate_lun_to_lungroup(self, lungroup_id, lun_id):
        """Associate lun to lungroup."""
        url = "/lungroup/associate"
        data = json.dumps({"ID": lungroup_id,
                           "ASSOCIATEOBJTYPE": "11",
                           "ASSOCIATEOBJID": lun_id})
        result = self.call(url, data)
        self._assert_rest_result(result, 'Associate lun to lungroup error.')

    def _add_mapping_view(self, name):
        url = "/mappingview"
        data = json.dumps({"NAME": name, "TYPE": "245"})
        result = self.call(url, data)
        self._assert_rest_result(result, 'Add mapping view error.')

        return result['data']['ID']

    def _associate_hostgroup_to_view(self, view_id, hostgroup_id):
        url = "/MAPPINGVIEW/CREATE_ASSOCIATE"
        data = json.dumps({"ASSOCIATEOBJTYPE": "14",
                           "ASSOCIATEOBJID": hostgroup_id,
                           "TYPE": "245",
                           "ID": view_id})
        result = self.call(url, data, "PUT")
        self._assert_rest_result(result, ('Associate host to mapping view '
                                 'error.'))

    def _associate_lungroup_to_view(self, view_id, lungroup_id):
        url = "/MAPPINGVIEW/CREATE_ASSOCIATE"
        data = json.dumps({"ASSOCIATEOBJTYPE": "256",
                           "ASSOCIATEOBJID": lungroup_id,
                           "TYPE": "245",
                           "ID": view_id})
        result = self.call(url, data, "PUT")
        self._assert_rest_result(
            result, 'Associate lungroup to mapping view error.')

    def _associate_portgroup_to_view(self, view_id, portgroup_id):
        url = "/MAPPINGVIEW/CREATE_ASSOCIATE"
        data = json.dumps({"ASSOCIATEOBJTYPE": "257",
                           "ASSOCIATEOBJID": portgroup_id,
                           "TYPE": "245",
                           "ID": view_id})
        result = self.call(url, data, "PUT")
        self._assert_rest_result(result, ('Associate portgroup to mapping '
                                 'view error.'))

    def hostgroup_associated(self, view_id, hostgroup_id):
        url_subfix = ("/mappingview/associate?TYPE=245&"
                      "ASSOCIATEOBJTYPE=14&ASSOCIATEOBJID=%s" % hostgroup_id)
        url = url_subfix
        result = self.call(url, None, "GET")
        self._assert_rest_result(result, 'Check hostgroup associate error.')

        if self._get_id_from_result(result, view_id, 'ID'):
            return True
        return False

    def lungroup_associated(self, view_id, lungroup_id):
        url_subfix = ("/mappingview/associate?TYPE=245&"
                      "ASSOCIATEOBJTYPE=256&ASSOCIATEOBJID=%s" % lungroup_id)
        url = url_subfix
        result = self.call(url, None, "GET")
        self._assert_rest_result(result, ('Check lungroup associate error.'))

        if self._get_id_from_result(result, view_id, 'ID'):
            return True
        return False

    def _portgroup_associated(self, view_id, portgroup_id):
        url = ("/mappingview/associate?TYPE=245&"
               "ASSOCIATEOBJTYPE=257&ASSOCIATEOBJID=%s" % portgroup_id)
        result = self.call(url, None, "GET")
        self._assert_rest_result(result, 'Check portgroup associate error.')

        if self._get_id_from_result(result, view_id, 'ID'):
            return True
        return False

    def find_array_version(self):
        url = "/system/"
        result = self.call(url, None)
        self._assert_rest_result(result, ('Find array version error.'))
        return result['data']['PRODUCTVERSION']

    def find_view_by_id(self, view_id):
        url = "/MAPPINGVIEW/" + view_id
        result = self.call(url, None, "GET")

        msg = 'Change hostlun id error.'
        self._assert_rest_result(result, msg)
        if 'data' in result:
            return result["data"]["AVAILABLEHOSTLUNIDLIST"]

    def remove_lun_from_lungroup(self, lungroup_id, lun_id):
        """Remove lun from lungroup."""
        url = ("/lungroup/associate?ID=%s&ASSOCIATEOBJTYPE=11"
               "&ASSOCIATEOBJID=%s" % (lungroup_id, lun_id))

        result = self.call(url, None, 'DELETE')
        self._assert_rest_result(
            result, 'Delete associated lun from lungroup error.')

    def do_mapping(self, lun_id, hostgroup_id, host_id, tgtportgroup_id=None):
        """Add hostgroup and lungroup to mapping view."""
        lungroup_name = constants.LUNGROUP_PREFIX + host_id
        mapping_view_name = constants.MAPPING_VIEW_PREFIX + host_id
        lungroup_id = self._find_lungroup(lungroup_name)
        view_id = self.find_mapping_view(mapping_view_name)
        map_info = {}

        LOG.info((
            'do_mapping, lun_group: %(lun_group)s, '
            'view_id: %(view_id)s, lun_id: %(lun_id)s.') %
            {'lun_group': lungroup_id,
             'view_id': view_id,
             'lun_id': lun_id})

        try:
            # Create lungroup and add LUN into to lungroup.
            if lungroup_id is None:
                lungroup_id = self._create_lungroup(lungroup_name)
            is_associated = self._is_lun_associated_to_lungroup(lungroup_id,
                                                                lun_id)
            if not is_associated:
                self.associate_lun_to_lungroup(lungroup_id, lun_id)

            if view_id is None:
                view_id = self._add_mapping_view(mapping_view_name)
                self._associate_hostgroup_to_view(view_id, hostgroup_id)
                self._associate_lungroup_to_view(view_id, lungroup_id)
                if tgtportgroup_id:
                    self._associate_portgroup_to_view(view_id, tgtportgroup_id)

            else:
                if not self.hostgroup_associated(view_id, hostgroup_id):
                    self._associate_hostgroup_to_view(view_id, hostgroup_id)
                if not self.lungroup_associated(view_id, lungroup_id):
                    self._associate_lungroup_to_view(view_id, lungroup_id)
                if tgtportgroup_id:
                    if not self._portgroup_associated(view_id,
                                                      tgtportgroup_id):
                        self._associate_portgroup_to_view(view_id,
                                                          tgtportgroup_id)

            version = self.find_array_version()
            if version >= constants.ARRAY_VERSION:
                aval_luns = self.find_view_by_id(view_id)
                map_info["lun_id"] = lun_id
                map_info["view_id"] = view_id
                map_info["aval_luns"] = aval_luns

        except Exception:
            LOG.error('Error occurred when adding hostgroup and lungroup to '
                      'view. Remove lun from lungroup now.')
            self.remove_lun_from_lungroup(lungroup_id, lun_id)
            raise VolumeBackendAPIException

        return map_info

    def delete_mapping(self, lun_id, host_name):
        if host_name and len(host_name) > constants.MAX_HOSTNAME_LENGTH:
            host_name = hash(host_name)
        host_id = self.find_host(host_name)
        if host_id:
            mapping_view_name = constants.MAPPING_VIEW_PREFIX + host_id
            view_id = self.find_mapping_view(mapping_view_name)
            if view_id:
                lungroup_id = self.find_lungroup_from_map(view_id)

        # Remove lun from lungroup.
        if lun_id and self.check_lun_exist(lun_id):
            if lungroup_id:
                lungroup_ids = self.get_lungroupids_by_lunid(lun_id)
                if lungroup_id in lungroup_ids:
                    self.remove_lun_from_lungroup(lungroup_id, lun_id)
                else:
                    LOG.info(('Lun is not in lungroup. '
                              'Lun id: %(lun_id)s. '
                              'lungroup id: %(lungroup_id)s.')
                             % {"lun_id": lun_id,
                                "lungroup_id": lungroup_id})
        else:
            LOG.error("Can't find lun on the array.")
            raise VolumeBackendAPIException

    def find_lungroup_from_map(self, view_id):
        """Get lungroup from the given map"""
        url_subfix = ("/mappingview/associate/lungroup?TYPE=256&"
                      "ASSOCIATEOBJTYPE=245&ASSOCIATEOBJID=%s" % view_id)
        url = url_subfix
        result = self.call(url, None, "GET")
        self._assert_rest_result(result, 'Find lun group from mapping view '
                                 'error.')
        lungroup_id = None
        if 'data' in result:
            # One map can have only one lungroup.
            for item in result['data']:
                lungroup_id = item['ID']

        return lungroup_id

    def check_lun_exist(self, lun_id):
        url = "/lun/" + lun_id
        result = self.call(url, None, "GET")
        error_code = result['error']['code']
        if error_code != 0:
            return False

        return True

    def change_description(self, lun_id, description):
        url = "/lun/"+lun_id
        data = json.dumps({"DESCRIPTION": description})
        result = self.call(url, data, "PUT")
        self._assert_rest_result(result, 'Change decription failed.')

    def get_lun_info(self, lun_id):
        url = "/lun/" + lun_id
        result = self.call(url, None, "GET")

        msg = 'Get volume error.'
        self._assert_rest_result(result, msg)
        self._assert_data_in_result(result, msg)

        return result['data']

    def add_fc_port_to_host(self, host_id, wwn):
        """Add a FC port to the host."""
        url = "/fc_initiator/" + wwn
        data = json.dumps({"TYPE": "223",
                           "ID": wwn,
                           "PARENTTYPE": 21,
                           "PARENTID": host_id})
        result = self.call(url, data, "PUT")
        self._assert_rest_result(result, 'Add FC port to host error.')

    def get_host_online_fc_initiators(self, host_id):
        url = "/fc_initiator?PARENTTYPE=21&PARENTID=%s" % host_id
        result = self.call(url, None, "GET")

        initiators = []
        if 'data' in result:
            for item in result['data']:
                if (('PARENTID' in item) and (item['PARENTID'] == host_id) and
                   (item['RUNNINGSTATUS'] == constants.FC_INIT_ONLINE)):
                    initiators.append(item['ID'])

        return initiators

    def get_host_initiators(self, init_type, host_id):
        url = ("/%(init_type)s_initiator?PARENTTYPE=21&PARENTID=%(host_id)s"
               % {"init_type": init_type, "host_id": host_id})
        result = self.call(url, None, "GET")

        initiators = []
        if 'data' in result:
            for item in result['data']:
                if ('PARENTID' in item) and (item['PARENTID'] == host_id):
                    initiators.append(item['ID'])

        return initiators

    def get_online_free_wwns(self):
        """Get online free WWNs.

        If no new ports connected, return an empty list.
        """
        url = "/fc_initiator?ISFREE=true&range=[0-8191]"
        result = self.call(url, None, "GET")

        msg = 'Get connected free FC wwn error.'
        self._assert_rest_result(result, msg)

        wwns = []
        if 'data' in result:
            for item in result['data']:
                wwns.append(item['ID'])

        return wwns

    def remove_host(self, host_id):
        url = "/host/%s" % host_id
        result = self.call(url, None, "DELETE")
        self._assert_rest_result(result, 'Remove host from array error.')

    def get_lungroupids_by_lunid(self, lun_id):
        """Get lungroup ids by lun id."""
        url = ("/lungroup/associate?TYPE=256"
               "&ASSOCIATEOBJTYPE=11&ASSOCIATEOBJID=%s" % lun_id)

        result = self.call(url, None, "GET")
        self._assert_rest_result(result, 'Get lungroup id by lun id error.')

        lungroup_ids = []
        if 'data' in result:
            for item in result['data']:
                lungroup_ids.append(item['ID'])

        return lungroup_ids

    def delete_lun(self, lun_id):
        lun_group_ids = self.get_lungroupids_by_lunid(lun_id)
        if lun_group_ids and len(lun_group_ids) == 1:
            self.remove_lun_from_lungroup(lun_group_ids[0], lun_id)

        url = "/lun/" + lun_id
        data = json.dumps({"TYPE": "11",
                           "ID": lun_id})
        result = self.call(url, data, "DELETE")
        self._assert_rest_result(result, 'Delete lun error.')

    def find_all_pools(self):
        url = "/storagepool"
        result = self.call(url, None)
        msg = ('Query resource pool error.')
        self._assert_rest_result(result, msg)
        self._assert_data_in_result(result, msg)
        return result

    def find_pool_info(self, pool_name=None, result=None):
        pool_info = {}
        if not pool_name:
            return pool_info

        if 'data' in result:
            for item in result['data']:
                if pool_name.strip() == item['NAME']:
                    # USAGETYPE means pool type.
                    if ('USAGETYPE' in item and
                       item['USAGETYPE'] == constants.FILE_SYSTEM_POOL_TYPE):
                        break
                    pool_info['ID'] = item['ID']
                    pool_info['CAPACITY'] = item.get('DATASPACE',
                                                     item['USERFREECAPACITY'])
                    pool_info['TOTALCAPACITY'] = item['USERTOTALCAPACITY']
                    break
        return pool_info

    def get_host_of_lun_map(self, lun_id):
        url = "/host/associate?ASSOCIATEOBJTYPE=11&ASSOCIATEOBJID="+lun_id
        result = self.call(url, None)
        msg = ('Query host of lun map failed.')
        self._assert_rest_result(result, msg)
        return result
