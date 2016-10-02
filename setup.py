# Copyright (c) 2015 Huawei Technologies Co., Ltd.
# See LICENSE file for details.

import codecs
from setuptools import setup, find_packages

# Get the long description from the DESCRIPTION.rst file
with codecs.open('DESCRIPTION.rst', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='huawei_oceanstor_flocker_plugin',
    version='1.0',
    description='Huawei OceanStor Backend Plugin for ClusterHQ/Flocker',
    long_description=long_description,
    author='xxx',
    author_email='xxx@huawei.com',
    url='https://github.com/huaweistorage/huawei-oceanstor-flocker-plugin',
    license='Apache 2.0',

    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: System Administrators',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 2.7',
        ],

    keywords='docker, flocker, plugin, python',
    packages=find_packages(exclude=['test*']),
    install_requires = ['uuid'],
    data_files=[('/etc/flocker/', ['example_huawei_agent.yml']),
                ('/etc/flocker/', ['example_flocker_huawei_conf.xml'])]
)
