Huawei storage driver for ClusterHQ/flocker
======================

## Description
This is a plugin driver for the [Flocker](https://clusterhq.com/) project

## Installation

**Tested on Ubuntu 14.04 LTS**

Make sure you have Flocker already installed. If not visit  [Install Flocker](https://docs.clusterhq.com/en/1.5.0/install/index.html)

**_Be sure to use /opt/flocker/bin/pip as this will install the driver into the right python environment_**

Install using pip
```bash
git clone https://github.com/huaweistorage/huawei-oceanstor-flocker-plugin.git
/opt/flocker/bin/pip install huawei-oceanstor-flocker-plugin/
```

You can optionally verify the correct packages are installed.
```bash
/opt/flocker/bin/pip list | grep -i huawei-oceanstor-flocker-plugin
huawei-oceanstor-flocker-plugin (1.0)
```


## Configure

Change the 'dataset' in the agent.yml
```bash
vi /etc/flocker/agent.yml
```
An example of agent.yml is below
```bash
version: 1
control-service:
  hostname: "<Insert IP/Hostname of Flocker-Control Service>"
  port: 4524
dataset:
  backend: "huawei_oceanstor_flocker_plugin"
  huawei_conf_file: "/etc/flocker/flocker_huawei_conf.xml"
```

Create a Huawei-customized driver configuration file. The file format is XML.
```bash
vi /etc/flocker/flocker_huawei_conf.xml
```
A minimal example of 'flocker_huawei_conf.xml' is below
```bash
<?xml version='1.0' encoding='UTF-8'?>
<config>
	<Storage>
		<Protocol>iSCSI</Protocol>
		<RestURL>https://x.x.x.x:8088/deviceManager/rest/</RestURL>
		<UserName>storage_username</UserName>
		<UserPassword>storage_password</UserPassword>
	</Storage>
    <LUN>
    	<StoragePool>pool_name</StoragePool>
    </LUN>
</config>
```
A full example of 'flocker_huawei_conf.xml' is below
```bash
<?xml version='1.0' encoding='UTF-8'?>
<config>
	<Storage>
		<Protocol>iSCSI</Protocol>
		<RestURL>https://x.x.x.x:8088/deviceManager/rest/</RestURL>
		<UserName>storage_username</UserName>
		<UserPassword>storage_password</UserPassword>
	</Storage>
    <LUN>
    	<StoragePool>pool_name</StoragePool>
    	<LUNType>Thick_or_Thin</LUNType>
    	<StripUnitSize></StripUnitSize>
    	<WriteType></WriteType>
    	<MirrorSwitch></MirrorSwitch>
    	<Prefetch></Prefetch>
    </LUN>
</config>
```


**Parameters in the Configuration File**

***_Mandatory parameters_***

| Parameter     | Default value |                        Description                                | 
| ------------- |:-------------:| :-----------------------------------------------------------------|
| Protocol      |      -        | Type of a connection protocol. The possible value is iSCSI or FC. |
| RestURL       |      -        | Access address of the REST interface.                             |
| UserName      |      -        | User name of a storage administrator.                             |
| UserPassword  |      -        | Password of a storage administrator.                              |
| StoragePool   |      -        | Name of a storage pool to be used.                                |

***_Optional parameters_***

| Parameter        | Default value |                    Description                                                                               | 
| ---------------- |:-------------:| :------------------------------------------------------------------------------------------------------------|
| LUNType          | Thin          | Type of the LUNs to be created. The value can be Thick or Thin.                                              |
| StripUnitSize    | 64            | Stripe depth of a LUN to be created. The unit is KB. This parameter is invalid when a thin LUN is created.   |
| WriteType        | 1             | Cache write type, possible values are: 1 (write back), 2 (write through), and 3 (mandatory write back).      |
| MirrorSwitch     | 1             | Cache mirroring or not, possible values are: 0 (without mirroring) or 1 (with mirroring).                    |
