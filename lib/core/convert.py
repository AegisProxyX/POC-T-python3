#!/usr/bin/python3
# -*- coding: utf-8 -*-
# author = syst1m

import sys
from lib.core.settings import IS_WIN, UNICODE_ENCODING


def singleTimeWarnMessage(message):  # Cross-linked function
    sys.stdout.write(message)
    sys.stdout.write("\n")
    sys.stdout.flush()


def stdoutencode(data):
    if isinstance(data, bytes):
        data = data.decode(UNICODE_ENCODING, errors='replace')
    text = str(data) if data is not None else ''
    encoding = sys.stdout.encoding or UNICODE_ENCODING
    return text.encode(encoding, errors='replace').decode(encoding)

