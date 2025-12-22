# -*- coding: utf-8 -*-
#pylint: disable=wrong-import-position

"""
JDR libs
"""

# Import libs
from . import config
from .system.logger import Logger, LoggerInterrupt

# create logger object
logger = Logger()

from . import system
from . import dice
from . import spell
from . import item
from . import character
