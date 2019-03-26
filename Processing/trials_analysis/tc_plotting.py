import sys
sys.path.append('./')
import numpy as np
import matplotlib
matplotlib.use("Qt5Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from database.NewTablesDefinitions import *
from database.database_fetch import *

from Processing.rois_toolbox.rois_stats import get_roi_at_each_frame, get_arm_given_rois, convert_roi_id_to_tag
from Processing.tracking_stats.math_utils import get_roi_enters_exits, line_smoother, calc_distance_between_points_2d, remove_tracking_errors, get_n_colors

from Processing.modelling.bayesian.hierarchical_bayes_v2 import Modeller as Bayesian


traces_fld = 'D:\\Dropbox (UCL - SWC)\\Rotation_vte\\Presentations\\ThesisCommitte\\HB traces'


def pr_sym_vs_asmy_get_traces():
    bayes = Bayesian()
    traces_fld = 'D:\\Dropbox (UCL - SWC)\\Rotation_vte\\Presentations\\ThesisCommitte\\HB traces'


    # Get data
    asym_exps = ["PathInt2", "PathInt2-L"]
    sym_exps = ["Square Maze", "TwoAndahalf Maze"]

    asym = [arm for arms in [get_trials_by_exp(e, 'true', ['escape_arm']) for e in asym_exps] for arm in arms]
    sym = [arm for arms in [get_trials_by_exp(e, 'true', ['escape_arm']) for e in sym_exps] for arm in arms]

    asym_origins = [arm for arms in [get_trials_by_exp(e, 'true', ['origin_arm']) for e in asym_exps] for arm in arms]
    sym_origins = [arm for arms in [get_trials_by_exp(e, 'true', ['origin_arm']) for e in sym_exps] for arm in arms]

    asym_sessions = [s for sessions in [get_sessuids_given_experiment(e) for e in asym_exps] for s in sessions]
    sym_sessions = [s for sessions in [get_sessuids_given_experiment(e) for e in sym_exps] for s in sessions]


    """
        LOOK AT EFFECT OF ARM OF ORIGIN
    """
    asym_r_ori = [e for o,e in zip(asym_origins, asym) if 'Right' in o]
    sym_r_ori = [e for o,e in zip(sym_origins, sym) if 'Right' in o]

    asym_l_ori = [e for o,e in zip(asym_origins, asym) if 'Left' in o]
    sym_l_ori = [e for o,e in zip(sym_origins, sym) if 'Left' in o]

    # DO SOME MODELLING
    if 1 == 1:
        asym_r_ori_int = [1 if 'Right' in e else 0 for e in asym_r_ori]
        asym_l_ori_int = [1 if 'Right' in e else 0 for e in asym_l_ori]
        trace, D, dp, t, tp = bayes.model_two_distributions(asym_r_ori_int, asym_l_ori_int)
        bayes.save_trace(trace, os.path.join(traces_fld, 'asym_origin.pkl'))
        

        sym_r_ori_int = [1 if 'Right' in e else 0 for e in sym_r_ori]
        sym_l_ori_int = [1 if 'Right' in e else 0 for e in sym_l_ori]
        trace,  D, dp, t, tp = bayes.model_two_distributions(sym_r_ori_int, sym_l_ori_int)
        bayes.save_trace(trace, os.path.join(traces_fld, 'sym_origin.pkl'))

    """
        LOOK AT THE EFFECT OF X POSITION
    """

    # Plot the probs of escaping left and right based on the position at stim onset
    asym_tracking = [arm for arms in [get_trials_by_exp(e, 'true', ['tracking_data']) for e in asym_exps] for arm in arms]
    sym_tracking = [arm for arms in [get_trials_by_exp(e, 'true', ['tracking_data']) for e in sym_exps] for arm in arms]

    asym_position_onset = [1 if 480 > tr[0, 0, 0] else 2 if 520 < tr[0, 0, 0] else 0 for tr in asym_tracking ]
    sym_position_onset = [1 if 480 > tr[0, 0, 0] else 2 if 520 < tr[0, 0, 0] else 0 for tr in sym_tracking ]

    asym_position_onset_pos = [tr[0, :2, 0] for tr in asym_tracking if (480 > tr[0, 0, 0] or 520 < tr[0, 0, 0])]
    sym_position_onset_pos = [tr[0, :2, 0] for tr in sym_tracking if (480 > tr[0, 0, 0] or 520 < tr[0, 0, 0])]

    asym_l_pos, asym_r_pos = [e for i,e in enumerate(asym) if asym_position_onset[i]==1], [e for i,e in enumerate(asym) if asym_position_onset[i]==2]
    sym_l_pos, sym_r_pos = [e for i,e in enumerate(sym) if sym_position_onset[i]==1], [e for i,e in enumerate(sym) if sym_position_onset[i]==2]

    # do some MODELLING
    if 1 == 1:
        asym_l_pos_int, asym_r_pos_int = [1 if 'Right' in e else 0 for e in asym_l_pos], [1 if 'Right' in e else 0 for e in asym_r_pos]
        sym_l_pos_int, sym_r_pos_int = [1 if 'Right' in e else 0 for e in sym_l_pos], [1 if 'Right' in e else 0 for e in sym_r_pos]
        

        trace,  D, dp, t, tp = bayes.model_two_distributions(asym_r_pos_int, asym_l_pos_int)
        bayes.save_trace(trace, os.path.join(traces_fld, 'asym_position.pkl'))

        trace,  D, dp, t, tp = bayes.model_two_distributions(sym_r_pos_int, sym_l_pos_int)
        bayes.save_trace(trace, os.path.join(traces_fld, 'sym_position.pkl'))


    """
        LOOK AT THE EFFECT OF ORIENTATION
    """

    asym_body_pos, asym_tail_pos = np.vstack([tr[0, :2, 0] for tr in asym_tracking ]), np.vstack([tr[0, :2, -1] for tr in asym_tracking ])
    sym_body_pos, sym_tail_pos = np.vstack([tr[0, :2, 0] for tr in sym_tracking ]), np.vstack([tr[0, :2, -1] for tr in sym_tracking ])

    asym_orient = calc_angle_between_vectors_of_points_2d(asym_body_pos.T, asym_tail_pos.T)
    sym_orient = calc_angle_between_vectors_of_points_2d(sym_body_pos.T, sym_tail_pos.T)

    asym_rorient, asym_lorient = [e for i,e in enumerate(asym) if asym_orient[i] <= 90-22.5], [e for i,e in enumerate(asym) if 180 >= asym_orient[i] >= 90+22.5]
    sym_rorient, sym_lorient = [e for i,e in enumerate(sym) if sym_orient[i] <= 90-22.5], [e for i,e in enumerate(sym) if 180 >= sym_orient[i] >= 90+22.5]
    
    asym_rorient_int, asym_lorient_int= [1 if 'Right' in e else 0 for e in asym_rorient], [1 if 'Right' in e else 0 for e in asym_lorient]
    sym_rorient_int, sym_lorient_int= [1 if 'Right' in e else 0 for e in sym_rorient], [1 if 'Right' in e else 0 for e in sym_lorient]

    trace, D, dp, t, tp = bayes.model_two_distributions(asym_rorient_int, asym_lorient_int)
    bayes.save_trace(trace, os.path.join(traces_fld, 'asym_orientation.pkl'))

    trace, D, dp, t, tp = bayes.model_two_distributions(sym_rorient_int, sym_lorient_int)
    bayes.save_trace(trace, os.path.join(traces_fld, 'sym_orientation.pkl'))

    plt.show()

""""
||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||
||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||
||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||
||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||
||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||
"""



def plot_two_dists_kde(d0, d1, d2, title, l1=None, l2=None, ax=None):
        colors = get_n_colors(6)

        if ax is None:
            f, ax = plt.subplots()

        c1, c2 = colors[2], colors[3]

        sns.kdeplot(d1, ax=ax, shade=True, color=c1, linewidth=2, alpha=.8, clip=[0, 1], label=l1)
        sns.kdeplot(d2, ax=ax, shade=True, color=c2, linewidth=2, alpha=.8, clip=[0, 1], label=l2)
        sns.kdeplot(d0, ax=ax, shade=False, color='k', linewidth=2, alpha=.25, clip=[0, 1], label='all')

        ax.set(title=title, xlim=[0, 1])
        ax.legend()

        if ax is None:
            f.savefig("D:\\Dropbox (UCL - SWC)\\Rotation_vte\\Presentations\\ThesisCommitte\\plots\\{}.svg".format(title.strip().split('-')[0]), format="svg")

def plotter():
    bayes = Bayesian()
    types = ['asym', 'sym']
    variables = ['origin', 'position', 'orientation']
    names = [t+'_'+v for t in types for v in variables]

    f, axarr = plt.subplots(nrows=2, ncols=len(variables))
    axarr = axarr.flatten()

    for name, ax in zip(sorted(names), axarr):
        trace = bayes.load_trace(savename=os.path.join(traces_fld, name+'.pkl'))
        tot_trace = bayes.load_trace(savename=os.path.join(traces_fld, 'hb_trace.pkl'))
        if 'asym' in name:
            tt = tot_trace['p_asym_grouped'].values
        else:
            tt = tot_trace['p_sym_grouped'].values

        plot_two_dists_kde(tt, trace['p_d1'].values, trace['p_d2'].values, name, 'R', 'L', ax=ax)

    f.savefig("D:\\Dropbox (UCL - SWC)\\Rotation_vte\\Presentations\\ThesisCommitte\\plots\\alternative_hp_stuff_things.svg", format="svg")



if __name__ == "__main__":
    plotter()
    plt.show()

