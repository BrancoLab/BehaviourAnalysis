import sys
sys.path.append('./')

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from collections import namedtuple
from itertools import combinations
import time
import scipy.stats as stats
import math
import matplotlib.mlab as mlab
import matplotlib as mpl
from scipy.signal import medfilt as median_filter
from sklearn.preprocessing import normalize
from scipy.integrate import cumtrapz as integral
import seaborn as sns
from tqdm import tqdm
import random

import multiprocessing as mp


mpl.rcParams['text.color'] = 'k'
mpl.rcParams['xtick.color'] = 'k'
mpl.rcParams['ytick.color'] = 'k'
mpl.rcParams['axes.labelcolor'] = 'k'

from database.NewTablesDefinitions import *

from Processing.tracking_stats.math_utils import *
from Utilities.file_io.files_load_save import load_yaml
from Processing.plot.tracking_onmaze_videomaker import VideoMaker
from Processing.trials_analysis.tc_plotting import plot_two_dists_kde
from Processing.modelling.bayesian.hierarchical_bayes_v2 import Modeller as Bayes
from database.database_fetch import *



class VTE:
    def __init__(self):
        self.zscore_th = .5
        self.video_maker = VideoMaker()
        self.bayes = Bayes()

    """
        =======================================================================================================================================================
            TABLE FUNCTIONS    
        =======================================================================================================================================================
    """

    def drop(self):
        ZidPhi.drop()
        sys.exit()

    def populate(self):
        zdiphi = ZidPhi()
        zdiphi.populate()

    @staticmethod
    def populate_vte_table(table, key, max_y = 450, displacement_th = 20, min_length=20):

        from database.NewTablesDefinitions import AllTrials

        # get tracking from corresponding trial
        trials = (AllTrials & "trial_id={}".format(key['trial_id']) & "is_escape='true'").fetch("tracking_data","session_uid", "experiment_name", "escape_arm")
        try:
            trials[0][0]
        except:
            # no trials
            return

        print("processing trial id: ", key['trial_id'])

        tracking, uid, experiment, escape_arm = trials[0][0], trials[1][0], trials[2][0], trials[3][0]
        # get xy for snout and platform at each frame
        x, y, platf = median_filter(tracking[:, 0, 1]), median_filter(tracking[:, 1, 1]),  median_filter(tracking[:, -1, 0])

        try:
            # Select the times between when the mice leave the catwalk and when they leave the threat platform
            # first_above_catwalk = np.where(y > 250)[0][0]
            first_above_catwalk = 0
            first_out_threat = np.where(platf != 1)[0][0]
        except:
            return

        n_steps = first_out_threat - first_above_catwalk
        if n_steps < min_length: return  # the trial started too close to max Y

        # using interpolation to remove nan from array
        x, y = fill_nans_interpolate(x[first_above_catwalk : first_out_threat]), fill_nans_interpolate(y[first_above_catwalk : first_out_threat])

        dx, dy = np.diff(x), np.diff(y)

        try:
            dphi = calc_angle_between_points_of_vector(np.vstack([dx, dy]).T)
        except:
            raise ValueError
        idphi = np.trapz(dphi)

        key['xy'] = np.vstack([x, y])
        key['dphi'] = dphi
        key['idphi'] = idphi
        key['session_uid'] = uid
        key['experiment_name'] = experiment
        key['escape_arm'] = escape_arm

        table.insert1(key)


    """
        =======================================================================================================================================================
            PLOTTING FUNCTIONS    
        =======================================================================================================================================================
    """

    def get_dataframe(self, experiment):
        trials = []
        for exp in experiment:
            t = (ZidPhi & "experiment_name='{}'".format(exp)).fetch('idphi', "xy", "escape_arm", "trial_id")
            trials.extend(t)

        data = pd.DataFrame.from_dict(dict(idphi=trials[0], xy=trials[1], escape_arm=t[2], trial_id=t[3]))
        data['zidphi'] = stats.zscore(data['idphi'].values)
        return data



    def zidphi_histogram(self, experiment=None, title=''):
        data = self.get_dataframe(experiment)
        zidphi = stats.zscore(data['idphi'])

        above_th = [1 if z>self.zscore_th else 0 for z in zidphi]
        perc_above_th = np.mean(above_th)*100

        f, ax = plt.subplots()

        ax.hist(zidphi, bins=16, color=[.4, .7, .4])
        ax.axvline(self.zscore_th, linestyle=":", color='k')
        ax.set(title=title+" {}% VTE".format(round(perc_above_th, 2)), xlabel='zIdPhi')


    def zidphi_tracking(self, experiment=None, title=''):
        data = self.get_dataframe(experiment)

        f, axarr = plt.subplots(ncols=2)
        for i, row in data.iterrows():
            if row['zidphi'] > self.zscore_th:
                axn = 1
            else:
                axn = 0

            axarr[axn].plot(row['xy'].T[:, 0], row['xy'].T[:, 1], alpha=.3, linewidth=2)

        axarr[0].set(title=title + ' non VTE trials', ylabel='Y', xlabel='X')
        axarr[1].set(title='VTE trials', ylabel='Y', xlabel='X')

    def vte_position(self, experiment=None, title=''):
        data = self.get_dataframe(experiment)

        f, axarr = plt.subplots(ncols=2)
        for i, row in data.iterrows():
            if row['zidphi'] > self.zscore_th:
                axn = 1
                c = 'r'
            else:
                axn = 0
                c = 'b'
            
            axarr.scatter(ow['xy'].T[0, 0], row['xy'].T[0, 1], c=c, alpha=.4, s=40)
        axarr[0].set(title=title + ' non VTE trials', ylabel='Y', xlabel='X')
        axarr[1].set(title='VTE trials', ylabel='Y', xlabel='X')



    """
        =======================================================================================================================================================
            VIDEO FUNCTIONS    
        =======================================================================================================================================================
    """


    def zidphi_videos(self, experiment=None, title='', fps=30, background='', vte=True):
        data = self.get_dataframe(experiment)

        data['rec_uid'] = [(AllTrials & "trial_id={}".format(i)).fetch("recording_uid")[0] for i in data['trial_id']]
        data['tracking'] = [(AllTrials & "trial_id={}".format(i)).fetch("tracking_data")[0] for i in data['trial_id']]

        data['origin'] = ['' for i in np.arange(len(data['rec_uid']))]
        data['escape'] = ['' for i in np.arange(len(data['rec_uid']))]
        data['stim_frame'] = ['' for i in np.arange(len(data['rec_uid']))]

        if vte:
            data = data.loc[data['zidphi'] > self.zscore_th]
        else:
            data = data.loc[data['zidphi'] <= self.zscore_th]

        self.video_maker.data = data
        self.video_maker.make_video(videoname = title, experimentname=background, fps=fps, 
                                    savefolder=self.video_maker.save_fld_trials, trial_mode=False)


    @staticmethod
    def make_parall_videos(arguments):
        processes = [mp.Process(target=self.zidphi_videos, args=arg) for arg in arguments]

        for p in processes:
            p.start()

        for p in processes:
            p.join()


    def parallel_videos(self):
        a1 = (['PathInt2', 'PathInt2 - L'], "Asymmetric Maze - NOT VTE", 40, 'PathInt2', False)
        a2 = (['PathInt2', 'PathInt2 - L'], "Asymmetric Maze - VTE", 40, 'PathInt2', True)
        a3 = (['Square Maze', 'TwoAndahalf Maze'], "Symmetric Maze - NOT VTE", 40, 'Square Maze', False)
        a4 = (['Square Maze', 'TwoAndahalf Maze'], "Symmetric Maze - VTE", 40, 'Square Maze', True)
        self.make_parall_videos([a1, a2, a3, a4])

        

    def parallel_videos2(self):
        a1 = (['Model based'], "MB - NOT VTE", 40, 'Model Based', False)
        a2 = (['Model Based', 'PathInt2 - L'], "MB - VTE", 40, 'Model Based', True)
        self.make_parall_videos([a1, a2])


    

    """
        =======================================================================================================================================================
            STATS FUNCTIONS    
        =======================================================================================================================================================
    """

    def pR_byVTE(self, experiment=None, title=None, target="Right_Medium"):
        data = self.get_dataframe(experiment)
        overall_escapes = [1 if e == target else 0 for e in list(data['escape_arm'].values)]
        vte_escapes = [1 if e == target else 0 for e in list(data.loc[data['zidphi'] >= self.zscore_th]['escape_arm'].values)]
        non_vte_escapes = [1 if e == target else 0 for e in list(data.loc[data['zidphi'] < self.zscore_th]['escape_arm'].values)]

        overall_pR = np.mean(overall_escapes)
        non_vte_pR = np.mean(non_vte_escapes)
        vte_pR = np.mean(vte_escapes)

        print("""
        Experiment {}
                overall pR: {}
                VTE pR:     {}
                non VTE pR: {}
        
        """.format(title, round(overall_pR, 2), round(vte_pR, 2), round(non_vte_pR, 2)))

        # boot strap
        n_vte_trials = len(list(data.loc[data['zidphi'] >= self.zscore_th]['escape_arm'].values))
        random_pR = []
        for i in np.arange(100000):
            random_pR.append(np.mean(random.choices(overall_escapes, k=n_vte_trials)))


        # Plot with bootstrap
        f, axarr = plt.subplots(ncols=2)
        axarr[0].hist(random_pR, bins=30, color=[.4, .7, .4], density=True)
        axarr[0].axvline(overall_pR, color='k', linestyle=':', label='Overall p(R)', linewidth=3)
        axarr[0].axvline(vte_pR, color='r', linestyle=':', label='VTE p(R)', linewidth=3)
        axarr[0].axvline(non_vte_pR, color='g', linestyle=':', label='nVTE p(R)', linewidth=3)
        axarr[0].set(title=title)
        axarr[0].legend()


        # plot with bayes
        vte_vs_non_vte, _, _, _, _ = self.bayes.model_two_distributions(vte_escapes, non_vte_escapes)
        vte_vs_all, _, _, _, _ = self.bayes.model_two_distributions(vte_escapes, overall_escapes)
        plot_two_dists_kde(vte_vs_all['p_d2'], vte_vs_all['p_d1'], vte_vs_non_vte['p_d2'], "bayesian posteriors",   l1="VTE", l2="not VTE", ax=axarr[1])





"""
    =======================================================================================================================================================
    =======================================================================================================================================================
    =======================================================================================================================================================
    =======================================================================================================================================================
"""
if __name__ == "__main__":
    vte = VTE()

    # vte.drop()
    # vte.populate()

    vte.vte_position(experiment=['PathInt2', 'PathInt2-L'], title="Asymmetric Maze - position")
    vte.vte_position(experiment=['Square Maze', 'TwoAndahalf Maze'], title='Symmetric Maze - position')

    # vte.pR_byVTE(experiment=['PathInt2', 'PathInt2-L'], title="Asymmetric Maze")
    # vte.pR_byVTE(experiment=['Square Maze', 'TwoAndahalf Maze'], title='Symmetric Maze')
    # vte.pR_byVTE(experiment=[ 'PathInt2-D'], title="Asymmetric Maze Dark")
    # vte.pR_byVTE(experiment=[ 'PathInt'], title="3 Arms", target="Centre")

    # vte.zidphi_histogram(experiment=['PathInt2', 'PathInt2 - L'], title="Asymmetric Maze")
    # vte.zidphi_histogram(experiment=['Square Maze', 'TwoAndahalf Maze'], title='Symmetric Maze')
    # vte.zidphi_histogram(experiment=['Model Based'], title="Model Based")
    # vte.zidphi_histogram(experiment=['FourArms Maze'], title="4 arm")


    # vte.zidphi_tracking(experiment=['PathInt2', 'PathInt2 - L'], title="Asymmetric Maze")
    # vte.zidphi_tracking(experiment=['Square Maze', 'TwoAndahalf Maze'], title='Symmetric Maze')
    # vte.zidphi_tracking(experiment=['Model Based'], title="Model Based")
    # vte.zidphi_tracking(experiment=['FourArms Maze'], title="4 arm")


    # vte.parallel_videos()
    # vte.parallel_videos2()



    plt.show()
