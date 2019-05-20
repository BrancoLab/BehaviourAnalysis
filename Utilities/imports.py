import sys
sys.path.append('./')

import pandas as pd
import os
from collections import namedtuple
import numpy as np
import cv2
from shutil import copyfile
from tqdm import tqdm 
from scipy import stats

if sys.platform == "darwin":
    import matplotlib
    matplotlib.use("Qt5Agg")
    
import matplotlib.pyplot as plt
import seaborn as sns

import time
import random
import warnings

if sys.platform != "darwin":
    import datajoint as dj
    from database.dj_config import start_connection
    from database.NewTablesDefinitions import *
    from database.auxillary_tables import *
    from database.database_fetch import *

from Utilities.file_io.files_load_save import *
from Utilities.video_and_plotting.video_editing import Editor

from Utilities.maths.math_utils import *

