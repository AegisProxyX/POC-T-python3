#!/usr/bin/python3
# -*- coding: utf-8 -*-
# author = syst1m

import os
import time
from lib.core.data import conf, logger
from lib.core.exception import ToolkitValueException
from lib.core.enums import API_MODE_NAME

def runApi():
    output = conf.API_OUTPUT
    dork = conf.API_DORK
    limit = conf.API_LIMIT
    logger.info('Activate %s API' % conf.API_MODE)
    if conf.API_MODE == API_MODE_NAME.ZOOMEYE:
        from lib.api.zoomeye.pack import ZoomEyeSearch
        anslist = ZoomEyeSearch(query=dork, limit=limit, type=conf.ZOOMEYE_SEARCH_TYPE, offset=conf.API_OFFSET)
    elif conf.API_MODE == API_MODE_NAME.SHODAN:
        from lib.api.shodan.pack import ShodanSearch
        anslist = ShodanSearch(query=dork, limit=limit, offset=conf.API_OFFSET)
    elif conf.API_MODE == API_MODE_NAME.GOOGLE:
        from lib.api.google.pack import GoogleSearch
        anslist = GoogleSearch(query=dork, limit=limit, offset=conf.API_OFFSET)
    elif conf.API_MODE == API_MODE_NAME.FOFA:
        from lib.api.fofa.pack import FofaSearch
        anslist = FofaSearch(query=dork, limit=limit, offset=conf.API_OFFSET)
    else:
        raise ToolkitValueException('Unknown API mode')

    tmpIpFile = os.path.join(output, '%s.txt' % (time.strftime('%Y%m%d%H%M%S')))
    with open(tmpIpFile, 'w', encoding='utf-8') as fp:
        for each in anslist:
            if isinstance(each, list):  # for ZoomEye web type
                each = each[0]
            fp.write(each + '\n')
    return tmpIpFile