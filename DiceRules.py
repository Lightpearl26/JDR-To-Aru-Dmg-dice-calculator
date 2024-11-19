#-*- coding: utf-8 -*-

# Create metainfos
__version__ = "1.0"
__author__ = "Franck Lafiteau"

# Import internal modules
from libs import Character as C

CL = C.CharacterList()
CL.update_images()
CL.save()