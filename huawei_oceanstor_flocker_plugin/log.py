# Copyright (c) 2015 Huawei Technologies Co., Ltd.
# See LICENSE file for details.

from eliot import Message, Logger

_logger = Logger()


class log():

    def error(self, msg):
        Message.new(Error="Huawei "+msg).write(_logger)

    def info(self, msg):
        Message.new(Info="Huawei "+msg).write(_logger)

LOG = log()
