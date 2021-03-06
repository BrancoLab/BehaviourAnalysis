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
import time
import random
import warnings
from shutil import copyfile
import pyexcel
import yaml



try: 
    dj.__version__
except: # ? onlu import tables if we havent already 
    try:
        import datajoint as dj
        from database.dj_config import start_connection 
        dbname, _ = start_connection()    
    except Exception as e:
        print("Could not connect to database: ", e)
    else:
        # print("Importing tables")
        from database.TablesDefinitionsV4 import *

from Utilities.matplotlib_config_figures import *

from Utilities.file_io.files_load_save import *
from Utilities.video_and_plotting.video_editing import Editor
from Utilities.maths.math_utils import *
from Utilities.maths.distributions import *
from Utilities.maths.filtering import *
from Utilities.constants import *

from Plotting.utils.plotting_utils import *
from Plotting.utils.plot_distributions import *
from Plotting.utils.colors import *


mpl.rc('text', usetex=False)
params = {
    'text.latex.preamble': ['\\usepackage{gensymb}'],
    # 'image.origin': 'lower',
    'image.interpolation': 'nearest',
    'image.cmap': 'gray',
    'axes.grid': False,
    'savefig.dpi': 150,  # to adjust notebook inline plot size
    'axes.labelsize': 12, # fontsize for x and y labels (was 10)
    'axes.titlesize': 12,
    'font.size': 12, # was 10
    'xtick.labelsize': 12,
    'ytick.labelsize': 12,
    'text.usetex': False,        # ! <----- use TEX
    'legend.fontsize': 14,
}
mpl.rcParams.update(params)
