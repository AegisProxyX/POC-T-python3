#!/usr/bin/python3
# -*- coding: utf-8 -*-
# author = syst1m

import queue
import sys
import importlib.util
import os 
from lib.core.data import th, conf, logger, paths
from lib.core.enums import API_MODE_NAME, TARGET_MODE_STATUS
from lib.core.settings import ESSENTIAL_MODULE_METHODS
from lib.core.exception import ToolkitValueException
from lib.controller.api import runApi
from thirdparty.IPy import IPy


def loadModule():
    filename = conf.MODULE_FILE_PATH
    logger.success('Load custom script: %s' % filename)
    spec = importlib.util.spec_from_file_location('_bayonet_poc', filename)
    if spec is None or spec.loader is None:
        raise ToolkitValueException('Cannot load Python script: %s' % filename)
    module = importlib.util.module_from_spec(spec)
    previous_path = sys.path[:]
    sys.path.insert(0, os.path.dirname(filename))
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = previous_path
    for name in ESSENTIAL_MODULE_METHODS:
        if not callable(getattr(module, name, None)):
            raise ToolkitValueException('Script must define callable %s()' % name)
    th.module_obj = module

def loadPayloads():
    logger.success('正在统计目标总数，统计时不会把全部目标载入内存……')
    if conf.TARGET_MODE == TARGET_MODE_STATUS.FILE:
        th.input_signature = _signature(conf.INPUT_FILE_PATH)
        th.total_count = sum(1 for _ in _lines(conf.INPUT_FILE_PATH))
        _check_input()
    elif conf.TARGET_MODE == TARGET_MODE_STATUS.RANGE:
        start, end = map(int, conf.I_NUM2.split('-'))
        th.total_count = max(0, end - start)
    elif conf.TARGET_MODE == TARGET_MODE_STATUS.IPMASK:
        th.total_count = IPy.IP(conf.NETWORK_STR).len()
    elif conf.TARGET_MODE == TARGET_MODE_STATUS.SINGLE:
        th.total_count = 1
    else:
        th.total_count = None
    if th.total_count is not None:
        logger.success('目标总数：%s；等待队列上限：1,000' % format(th.total_count, ','))
    th.queue = queue.Queue(maxsize=1000)
    modes = {TARGET_MODE_STATUS.FILE: file_mode,
             TARGET_MODE_STATUS.RANGE: int_mode,
             TARGET_MODE_STATUS.IPMASK: net_mode,
             TARGET_MODE_STATUS.SINGLE: single_target_mode,
             TARGET_MODE_STATUS.API: api_mode}
    if conf.TARGET_MODE not in modes:
        raise ToolkitValueException('Invalid target mode')
    th.target_source = modes[conf.TARGET_MODE]()

def _lines(filename):
    with open(filename, encoding='utf-8-sig') as stream:
        for line in stream:
            target = line.strip()
            if target:
                yield target

def _signature(filename):
    stat = os.stat(filename)
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)

def _check_input():
    if _signature(conf.INPUT_FILE_PATH) != th.input_signature:
        raise ToolkitValueException('目标文件在统计或扫描期间发生变化，请保持输入文件不变后重新运行。')

def file_mode():
    _check_input()
    yield from _lines(conf.INPUT_FILE_PATH)
    _check_input()

def int_mode():
    start, end = map(int, conf.I_NUM2.split('-'))
    for number in range(start, end):
        yield str(number)

def net_mode():
    for address in IPy.IP(conf.NETWORK_STR):
        yield str(address)

def single_target_mode():
    yield str(conf.SINGLE_TARGET_STR)

def api_mode():
    conf.API_OUTPUT = os.path.join(paths.DATA_PATH, conf.API_MODE)
    os.makedirs(conf.API_OUTPUT, exist_ok=True)
    filename = runApi()
    th.total_count = sum(1 for _ in _lines(filename))
    logger.success('搜索完成，目标总数：%s' % format(th.total_count, ','))
    yield from _lines(filename)
