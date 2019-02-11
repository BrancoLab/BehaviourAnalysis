import sys
sys.path.append('./')
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd
from pandas.plotting import scatter_matrix
from collections import namedtuple
from itertools import combinations
import time
import yaml

from database.NewTablesDefinitions import *
from database.dj_config import start_connection

from Processing.tracking_stats.math_utils import line_smoother
from Utilities.file_io.files_load_save import load_yaml
from Processing.rois_toolbox.rois_stats import get_roi_at_each_frame
from Processing.tracking_stats.math_utils import calc_distance_between_points_2d


class Trip:
    def __init__(self):
        """
            fake class used to store data about each shelter - threat - shelter trip
        """
        self.shelter_exit = None        # The frame number at which the mouse leaves the shelter
        self.threat_enter = None        # The frame number at which the mouse enters the therat
        self.threat_exit = None         # The frame number at which the mouse leaves the threat
        self.shelter_enter = None       # The frame number at which the mouse reaches the shelter
        self.time_in_shelter = None     # time spent in the shelter before leaving again    
        self.tracking_data = None       # Numpyu array with X, Y, S, O... at each frame
        self.is_trial = None            # Bool
        self.recording_uid = None       # Str
        self.duration = None            # Escape duration from levae threat to at shelter in seconds
        self.is_escape = None           # Bool
        self.escape_arm = None           # Str
        self.origin_arm = None
        self.experiment_name = None     # Str
        self.max_speed = None         #
        self.stim_frame = None
        
    def _as_dict(self):
        return self.__dict__


class analyse_all_trips:
    """ 
        get all trips data from the database
        divide them based on arm of orgin and return and trial or not
    """

    def __init__(self, erase_table=False, fill_in_table=False):
        self.debug = False   # Plot stuff to check things
        if erase_table:
            self.erase_table()

        if fill_in_table: # Get tracking data
            self.table = AllTrips()
            self.fetch_data()

            # Prepare variables
            self.exclude_by_exp = True
            self.naughty_experiments = ['Lambda Maze', ]
            self.good_experiments = ['PathInt2', 'Square Maze', 'TwoAndahalf Maze', 'PathInt', 'FlipFlop Maze', 'FlipFlop2 Maze']
            self.all_trips = []

            # Get all the times the mouse goes from the threat to the shelter
            print('     ... getting trips')
            self.get_trips()

            # Insert good trips into trips table
            
            self.insert_trips_in_table()


    def erase_table(self):
        """ drops table from DataJoint database """
        AllTrips.drop()
        print('Table erased, exiting...')
        sys.exit()

    def fetch_data(self):
        """ 
            Gets the relevant data from the the DataJoint database
        """ 

        print('     ... fetching data')
            
        fetched = (TrackingData.BodyPartData & 'bpname = "body"').fetch()

        # Get BODY tracking data
        all_bp_tracking = pd.DataFrame(fetched)
        self.tracking = all_bp_tracking.loc[all_bp_tracking['bpname'] == 'body']

        # Get all stimuli
        self.stimuli = pd.DataFrame(BehaviourStimuli.fetch())

        print('... ready')

    #####################################################################
    #####################################################################

    def get_rois_enters_exits(self, tr, rois_coords=None):
        """
            Returns a dict where for each roi there is a tuple with a list of all the frames at which the mouse enters the roi and a list
            for when it exits the roi
        """

        def remove_errors(times, roi, tr):
            """
                Excludes the events that happened too far from the ROI
            """
            th = 200

            # Need to flip ROIs Y axis to  match tracking
            roix, roiy = roi[0], roi[1]
            dist_from_midline = 500 - roiy
            roiy = 500 + dist_from_midline

            good = []
            for t in times:
                x,y = tr[t, 0], tr[t, 1]
                # distance = abs(calc_distance_between_points_2d((x,y), roi))
                if abs(roix-x)<th and abs(roiy-y)<th:
                    good.append(t)
            return good

        # Define variables
        in_rois = {}
        in_roi_tup = namedtuple('inroi', 'ins outs') # For each roi store the times the mouse enters and exits
        rois = dict(shelter=0, threat=1) 

        roi_at_each_frame = tr[:, -1]

        # Loop over each desired roi
        in_roi_times = []
        for i, (roi, cc) in enumerate(rois.items()):
            in_roi = np.where(roi_at_each_frame==cc)[0]
            in_roi_times.append(in_roi)

            # get times at which it enters and exits
            xx = np.zeros(tr.shape[0])
            xx[in_roi] = 1
            enter_exit = np.diff(xx)
            enters, exits = np.where(np.diff(xx)>0)[0], np.where(np.diff(xx)<0)[0]

            # Exclude entry and exit time that happened too far from the ROIs centre (likely errors)
            good_entries, good_exits = remove_errors(enters, rois_coords[roi[0]], tr ), remove_errors(exits, rois_coords[roi[0]], tr)
            in_rois[roi] = in_roi_tup(list(good_entries), list(good_exits))

        if self.debug:
            f, ax = plt.subplots()
            ax.scatter(tr[:, 0], tr[:, 1], c=[.2, .2, .2], alpha=.8)
            for c, times in zip(['b', 'y'], in_roi_times):
                ax.scatter(tr[times, 0], tr[times, 1], c=c)
            ax.scatter(tr[in_rois['shelter'].ins, 0], tr[in_rois['shelter'].ins, 1], c='r')
            ax.scatter(tr[in_rois['threat'].ins, 0], tr[in_rois['threat'].ins, 1], c='g')
            ax.scatter(tr[in_rois['shelter'].outs, 0], tr[in_rois['shelter'].outs, 1], c='r', alpha=.5)
            ax.scatter(tr[in_rois['threat'].outs, 0], tr[in_rois['threat'].outs, 1], c='g', alpha=.5)
            ax.plot(rois_coords['s'][0], (500 + (500-rois_coords['s'][1])), '+', color='r', label='shelter')
            ax.plot(rois_coords['t'][0], (500 + (500-rois_coords['t'][1])), '+', color='g', label='threat')
            ax.legend()

            # plt.show()

        return in_rois

    def get_complete_trips(self, in_rois):
        """
            For each time the mouse leaves the shelter, only keep the last time before the mouse got to the threat and back. 
            i.e. if the mouse leaves the shelter briefly and then returns before doing a complete trip, disregard. 
        """
        good_trips = []

        for sexit in in_rois['shelter'].outs:
            # get time in which it returns to the shelter 
            try:
                next_in = [i for i in in_rois['shelter'].ins if i > sexit][0] # Next time the mouse returns to the shelter
                time_in_shelter = [i for i in in_rois['shelter'].outs if i > next_in][0]-next_in  # time spent in shelter after return
            except:
                if sexit == in_rois['shelter'].outs[-1]: 
                    next_in = [i for i in in_rois['shelter'].ins if i > sexit]
                    if not next_in: continue
                    else:
                        next_in = next_in[0]
                        time_in_shelter == -1
                else:
                    continue
                    # raise ValueError

            # Check if it reached the threat after leaving the shelter
            at_threat = [i for i in in_rois['threat'].ins if i > sexit and i < next_in]              
            if at_threat:
                tenter = at_threat[0]
                try:
                    texit = [t for t in in_rois['threat'].outs if t>=tenter and t<=next_in][-1]
                except:
                    raise ValueError
                    pass  # didn't reach threat, don't append the good times
                else:
                    gt = Trip()  # Instantiate an instance of the class and populate it with data
                    gt.shelter_exit = sexit
                    gt.threat_enter = tenter
                    gt.threat_exit = texit
                    gt.shelter_enter = next_in
                    gt.time_in_shelter = time_in_shelter
                    good_trips.append(gt)

        return good_trips

    def inspect_trips(self, complete_trips, exp, row, tr):
        """
            For each trip, check if it includes a trial, on which arm the return happened. 
            How long the return lasted, if it classifies as an escape...
        """

        def get_arm_given_rois(roi_id, roi_ids, y_midpoint):
            # ! Based on the IDs of the platforms. Not very elegant but works it seems
            if 22.0 == roi_id:
                arm_taken = 'Centre'
            elif roi_id in [9.0, 5.0, 15.0, 14.0]:
                arm_taken = 'Right_Far'
            elif roi_id in [8.0, 2.0, 10.0, 11.0]:
                arm_taken = 'Left_Far'
            elif roi_id in [13.0, 6.0, 18.0]:
                if 22.0 in roi_ids:
                    arm_taken = "Centre"
                elif 14.0 in roi_ids[y_midpoint:y_midpoint+60] or 5.0 in roi_ids[y_midpoint:y_midpoint+60]:
                    arm_taken = 'Right_Far'
                else:
                    arm_taken = 'Right_Medium'
            elif roi_id in [12.0, 3.0, 17.0]:
                if 22.0 in roi_ids:
                    arm_taken = 'Centre'
                elif 11.0 in roi_ids[y_midpoint:y_midpoint+60] or 2.0 in roi_ids[y_midpoint:y_midpoint+60]:
                    arm_taken = 'Left_Far'
                else: 
                    arm_taken = 'Left_Medium'
            else:
                raise ValueError
            return arm_taken


        warnings.warn('Lots of hardcoded variables')
        for g in complete_trips:
            # Get the stimuli of this recording and see if one happened between when the mouse left the shelter and when it leaves the threat
            rec_stimuli = self.stimuli.loc[self.stimuli['recording_uid'] == row['recording_uid']]
            stims_in_time = [s for s in rec_stimuli['stim_start'].values if g.threat_enter<s<g.threat_exit]
            
            if stims_in_time:
                # Sanity check
                has_stim = 'true'
                stim_frame = stims_in_time[-1]
            else:
                has_stim = 'false'
                stim_frame = -1

            # Get remaining variables
            endtime = g.shelter_enter+g.time_in_shelter  # Take tracking data up to this time
            tracking_data = tr[g.shelter_exit:endtime, :]
            escape_start, escape_end = g.threat_exit -g.shelter_exit,  g.shelter_enter-g.shelter_exit
            outward_trip_end = g.threat_enter - g.shelter_exit

            # Ignore returns that are faster than 1s, probably errors
            if escape_end-escape_start <= 30*.5: continue # ! hardcoded fps


            # Get the arm of escape
            try:
                y_midpoint = np.where(tracking_data[escape_start:escape_end,1]>=550)[0][0]  # midpoint on the y axis, used to check which arm was takem
                y_midpoint_origin = np.where(tracking_data[0:outward_trip_end,1]<=550)[0][0]
            except:
                raise ValueError
                print('smth went wrong')
                continue

            escape_rois_ids = np.trim_zeros(tracking_data[escape_start:escape_end, -1])
            escape_rois_id = escape_rois_ids[y_midpoint]
            escape_arm = get_arm_given_rois(escape_rois_id, escape_rois_ids, y_midpoint)
            
            # Get the arm of origin
            # ! this bit of code is very ugly, need a more elegant solution
            origin_rois_ids = np.trim_zeros(tracking_data[0:outward_trip_end, -1])
            origin_rois_ids = origin_rois_ids[origin_rois_ids > 2]
            origin_rois_ids_c = origin_rois_ids.copy()
            origin_rois_id = origin_rois_ids[-1]
            if origin_rois_id < 1: 
                # Something went wrong, try removing frames with abnormally high speed values to see if the problem is due to tracking errors
                high_velocity_frames = np.where(tracking_data[0:outward_trip_end,2] >= 28)[0]
                origin_rois_ids_c[high_velocity_frames] =  origin_rois_ids_c[high_velocity_frames-1] =  origin_rois_ids_c[high_velocity_frames+1] = -1
                origin_rois_ids = origin_rois_ids_c[origin_rois_ids_c > 2]
                origin_rois_id = origin_rois_ids[-1]
                if origin_rois_id == np.nan: raise ValueError
                # raise ValueError

            origin_arm = get_arm_given_rois(origin_rois_id, origin_rois_ids, y_midpoint)

            # Get the duration of the escape
            duration = (g.shelter_enter - g.threat_exit)/30 # ! hardcoded fps
            smooth_speed = line_smoother(tracking_data[:,2])
            max_speed = np.percentile(smooth_speed, 85)

            # ! arbritary
            duration_lims = dict(Left_Far=9,
                            Left_Medium=6,
                            Centre=4,
                            Right_Medium=6,
                            Right_Far=9)

            if duration <= duration_lims[escape_arm]: # ! hardcoded arbritary variable
                is_escape = 'true'
            else:
                is_escape = 'false'

            # Update more variables of the trip class
            g.tracking_data = tracking_data
            g.is_trial = has_stim
            g.recording_uid = row['recording_uid']
            g.duration = duration
            g.max_speed = max_speed
            g.is_escape = is_escape
            g.escape_arm = escape_arm
            g.experiment_name = exp
            g.origin_arm = origin_arm
            g.stim_frame = stim_frame

            self.all_trips.append(g)

    def get_trips(self):
        """
            Gets all the time the mouse leaves the shelter, goes to threat and then goes back to the shelter. 
            Once all the trips are identified, the tracking data for those time intervals are selected, the escape arm is classified
            and the trip is checked to see if its an escape and if it happened after a trial
        """
        # Get recordings and sessions data
        recordings = pd.DataFrame(Recordings().fetch())
        sessions = pd.DataFrame(Sessions().fetch())
        templates = Templates.fetch()

        # Get entries already in table
        in_table = pd.DataFrame(self.table.fetch())['recording_uid'].values

        # Loop over each entry in the tracking table
        for idx, row in self.tracking.iterrows():
            """
                FETCH AND EXCLUDE DATA
            """
            if self.exclude_by_exp:    
                # To exclude trials from unwanted experiment get the experiment matching the tracking data
                rec = recordings.loc[recordings['recording_uid'] == row['recording_uid']]
                # if rec['recording_uid'].values[0] in in_table: continue



                sess = sessions.loc[sessions['session_name'] == rec['session_name'].values[0]]
                exp = sess['experiment_name'].values[0]
                        
                if exp in self.naughty_experiments: continue
                if exp not in self.good_experiments: continue

            # Get the tracking data as a numpy array
            tr = row['tracking_data']
            print(row['recording_uid'], idx)

            # Get the templates position
            templates_idx = [i for i, t in enumerate(templates) if t['uid'] == row['uid']][0]
            rois_coords = pd.DataFrame(templates).iloc[templates_idx]

        """
                GET ALL THE TIMES THE MOUSE IS IN SHELTER OR IN THREAT
            """
            in_rois = self.get_rois_enters_exits(tr, rois_coords)


            """
                GET ALL THE TIMES A MOUSE DOES A COMPLETE S-T-S TRIP
            """
            # ! THIS MIGHT NEED TO CHANGE ?
            complete_trips = self.get_complete_trips(in_rois)

            """
                INSPECT THE TRIPS TO ADD FURTHER DETAILS
            """
            self.inspect_trips(complete_trips, exp,row, tr)


    def insert_trips_in_table(self):
        for i, trip in enumerate(self.all_trips): 
            key = trip._as_dict() 
            key['trip_id'] = i
            try:
                self.table.insert1(key)
                print('inserted: ', key['recording_uid'])
            except:
                print(' !!! - did not insert !!! - ', key['recording_uid'])


"""
############################################################################################################################
############################################################################################################################
############################################################################################################################
############################################################################################################################
"""



def check_table_inserts(table):
    data = pd.DataFrame(table.fetch())

    # Plot XY traces sorted by arm taken
    arms = set(data['escape_arm'].values)
    f, axarr = plt.subplots(3, 2, facecolor =[.2,  .2, .2])
    axarr = axarr.flatten()

    colors =['r', 'b', 'm', 'g', 'y']
    for i, (arm, ax) in enumerate(zip(arms, axarr)):
        sel = data.loc[data['escape_arm'] == arm]
        sel2 = data.loc[data['origin_arm'] == arm]
        # for idx, row in sel.iterrows():
        #     t0, t1, t2 = row['threat_enter']-row['shelter_exit'], row['shelter_enter']-row['shelter_exit'], row['threat_exit']-row['shelter_exit']
        #     tracking = row['tracking_data']
        #     ax.scatter(tracking[t2:t1, 0], tracking[t2:t1, 1],c=tracking[t2:t1, -1],    s=1, alpha=.5)

        for idx, row in sel2.iterrows():
            t0, t1, t2 = row['threat_enter']-row['shelter_exit'], row['shelter_enter']-row['shelter_exit'], row['threat_exit']-row['shelter_exit']
            tracking = row['tracking_data']
            ax.scatter(tracking[0:t0, 0], tracking[0:t0, 1],c=tracking[0:t0, -1],    s=1, alpha=.5)

        ax.set(title=arm, facecolor=[.2, .2, .2], xlim=[0, 1000], ylim=[200, 800])
    axarr[-1].set(facecolor=[.2, .2, .2])
    plt.show()


def check_all_trials_included(table):
    """
    In principle all trials should be included in All Returns, lets check
    """
    data = pd.DataFrame(table.fetch())
    recordings = Recordings().fetch("recording_uid")
    stimuli = pd.DataFrame(BehaviourStimuli.fetch())

    fetched = (TrackingData.BodyPartData & 'bpname = "body"').fetch()
    all_bp_tracking = pd.DataFrame(fetched)
    body_tracking = all_bp_tracking.loc[all_bp_tracking['bpname'] == 'body']
    
    for i, rec in enumerate(recordings):
        print('Checking rec {} of {}'.format(i, len(recordings)))
        r_stim_times = stimuli.loc[stimuli['recording_uid'] == rec]['stim_start'].values
        rtrips = data.loc[(data['recording_uid'] == rec)&(data['is_trial']=='true')]

        if not np.any(rtrips['recording_uid'].values): continue

        for si, stim_time in enumerate(r_stim_times):
            if stim_time == -1: continue # just a place holder empty stim table entry

            # Check if there is a trial trip that includes it
            entry_in_t_before_stim = np.where(rtrips['threat_enter'].values <= stim_time)[0]

            if not len(entry_in_t_before_stim): 
                # raise ValueError('Didnt find any good time')
                print('     Didnt find any good time')
                continue
            else:
                last_entry_index = entry_in_t_before_stim[-1]

            try:
                prev_enter = rtrips['threat_enter'].values[last_entry_index]
                next_exit = rtrips['threat_exit'].values[last_entry_index]
            except:
                raise ValueError('      smth went wrong')
            else:
                if not prev_enter < stim_time < next_exit: 
                    rec_tracking = body_tracking.loc[body_tracking['recording_uid']==rec]['tracking_data'].values[0]
                    t0, t1 = -600, 600
                    plt.scatter(rec_tracking[stim_time+t0:stim_time+t1, 0], rec_tracking[stim_time+t0:stim_time+t1, 1], c=rec_tracking[stim_time+t0:stim_time+t1, -1])


                    # raise ValueError('Timings wrong')
                    print('     Timings wrong')
                    print('     {} - stim {} of {}'.format(rec, si, len(r_stim_times)))

                    tracking = rtrips['tracking_data'].values[last_entry_index]
                    plt.scatter(tracking[:, 0], tracking[:, 1])

    # If we got here everything was good
    print('All trials are included')



"""
############################################################################################################################
############################################################################################################################
############################################################################################################################
############################################################################################################################
"""


if __name__ == '__main__':

    analyse_all_trips(erase_table=False, fill_in_table=True)

    
    # check_table_inserts(AllTrips())

    # check_all_trials_included(AllTrips())

    print(AllTrips())

