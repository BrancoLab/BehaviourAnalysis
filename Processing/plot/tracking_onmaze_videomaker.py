import sys
sys.path.append('./')
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import matplotlib.image as mpimg
import pandas as pd
import os
from tqdm import tqdm
import seaborn as sns
import math

from database.NewTablesDefinitions import *
from database.database_fetch import *

from Processing.rois_toolbox.rois_stats import get_roi_at_each_frame, get_arm_given_rois, convert_roi_id_to_tag
from Processing.tracking_stats.math_utils import *
from Utilities.video_and_plotting.video_editing import Editor

class VideoMaker:
    def __init__(self):
        self.save_fld_trials = 'D:\\Dropbox (UCL - SWC)\\Rotation_vte\plots\\all_trials'
        self.save_fld_explorations = 'D:\\Dropbox (UCL - SWC)\\Rotation_vte\plots\\explorations'
        self.escapes = 'true'

        self.to_fetch = ['experiment_name', 'tracking_data', 'fps', 'number_of_trials', 'trial_number', 
                         'recording_uid', 'stim_frame', 'escape_arm', 'origin_arm', 'is_escape', 'trial_id']


    """
    #####################################################################################################################################################################################################################################################
    #####################################################################################################################################################################################################################################################
    #####################################################################################################################################################################################################################################################
    """

    def plot_all_trials(self):

        t, r, n = [], [], []

        for tr_id in tqdm(AllTrials.fetch("trial_id")):
            escape,recuid, uid, experiment, tracking = (AllTrials & 'trial_id={}'.format(tr_id)).fetch('is_escape', 'recording_uid', 'session_uid', 'experiment_name', 'tracking_data')
            
            if escape == 'false': continue
            recuid = recuid[0]
            uid = uid[0]
            session = get_sessname_given_sessuid(uid)[0]
            videoname = session + '_all_trials'
            fps = get_videometadata_given_recuid(recuid)
            t.append(tracking)
            r.append(recuid)
            n.append('')
        self.data = self.make_dataframe(t, r, n)

        self.make_video(videoname=videoname, experimentname="all_trials", savefolder=self.save_fld_explorations, fps=fps,
                        trial_mode=None, frame_title=session)


    def first_trial(self, first_escape=True):
        print("Making video of first trials")
        t, r, stfr, ors, esc = [], [], [], [], []

        sessions = sorted(set(AllTrials.fetch("session_uid")))

        for uid in tqdm(sessions):
            is_escape, escape_arm, origin_arm, recuid, experiment, tracking, stimframes = (AllTrials & 'session_uid={}'.format(uid)).fetch('is_escape','escape_arm', 'origin_arm', 'recording_uid', 'experiment_name', 'tracking_data', 'stim_frame')
            
            if first_escape:
                if 'true' in is_escape:
                    is_escape_index = list(is_escape).index('true')
                else: continue
            else: is_escape_index = 0

            recuid = recuid[is_escape_index]
            session = get_sessname_given_sessuid(uid)[0]
            tracking = tracking[is_escape_index]
            t.append(tracking)
            r.append(recuid)
            ors.append(origin_arm[is_escape_index])
            esc.append(escape_arm[is_escape_index])
            stfr.append(stimframes[is_escape_index])

        self.data = self.make_dataframe(t, r, stim_frame=stfr, origin=ors, escape=esc)

        self.make_video(videoname='first_escapes', experimentname="all_trials", savefolder=self.save_fld_trials, fps=30,
                        trial_mode=True)

    
    def make_explorations_video(self):
        ids = AllExplorations.fetch('exploration_id')

        for exp_id in ids:
            uid, experiment, tracking, start = (AllExplorations & 'exploration_id={}'.format(exp_id)).fetch('session_uid', 'experiment_name', 'tracking_data', 'exploration_start')
            uid = uid[0]
            session = get_sessname_given_sessuid(uid)
            recuid = get_recordings_given_sessuid(uid)[0]['recording_uid']
            videoname = session[0] + '_exploration'
            fps = get_videometadata_given_recuid(recuid)
            self.data = self.make_dataframe(tracking, recuid, [''])

            self.make_video(videoname=videoname, experimentname=experiment[0], savefolder=self.save_fld_explorations, fps=fps*4,
                            trial_mode=None, frame_title=session[0], start_frame=0)


    @staticmethod
    def make_dataframe(tracking, recuid, trialid=None, stim_frame=None, origin=None, escape=None):
        if trialid is None: trialid = ['' for x in tracking]
        if stim_frame is None: stim_frame = ['' for x in tracking]
        if origin is None: origin = ['' for x in tracking]
        if escape is None: escape = ['' for x in tracking]


        d = dict(
            rec_uid = recuid,
            trial_id = trialid, 
            tracking = tracking,
            stim_frame = stim_frame,
            origin = origin, 
            escape = escape
        )

        return pd.DataFrame.from_dict(d)


    """
    #####################################################################################################################################################################################################################################################
    #####################################################################################################################################################################################################################################################
    #####################################################################################################################################################################################################################################################
    """

    def make_video(self, videoname=None, experimentname=None, savefolder=None, fps=40, trial_mode=True, frame_title='', start_frame=0):
        # check if file exists
        complete_video_path = os.path.join(savefolder, videoname+'.mp4')
        if os.path.isfile(complete_video_path) and os.path.getsize(complete_video_path) > 10000:
            print(videoname, " exists already ")
            return
        else:
            print("saving ", videoname)

        # get maze model
        maze_model = get_maze_template(exp=experimentname)

        # Define body parts and indexes for body and head contours
        bps = ['body', 'snout', 'left_ear', 'right_ear', 'neck', 'tail_base']
        body_idxs = [2, 1, 3, 5]
        head_idxs = [2, 1, 3, 0]

        # Cropping coordinates for threat area
        threat_cropping = ((500, 950), (400, 600))

        # open openCV writer
        video_editor = Editor()
        if trial_mode: width_factor = 2
        else: width_factor = 1
        writer = video_editor.open_cvwriter(complete_video_path, w=maze_model.shape[0]*width_factor, h=maze_model.shape[1],
                                            framerate = fps, iscolor=True)
        
        # loop over each trial
        stored_contours = []
        for row_n, row in self.data.iterrows():
            print("Processing trial: ", row_n)
            if len(row['tracking'].shape) == 3:
                tr = row['tracking']
            else: tr = row['tracking'][0]
            
            # shift all tracking Y up by 10px to align better
            trc = tr.copy()
            trc[:, 1, :] = np.add(trc[:, 1, :], 10)
            tr = trc
            tot_frames = tr.shape[0]
                
            # get tracking data for the different contours to draw
            body_contour = tr[start_frame:, :, body_idxs]
            head_contour = tr[start_frame:, :, head_idxs]
            body_ellipse = tr[start_frame:, :, [0, 5]]

            # Compute body and head angle vectors
            body_angle = calc_angle_between_vectors_of_points_2d(tr[:, :2, -1].T, tr[:, :2, 0].T)
            head_angle = calc_angle_between_vectors_of_points_2d(tr[:, :2, 0].T, tr[:, :2, 1].T)

            # Prepare trial background [based on previous trials]            
            trial_background = self.prepare_background(row_n, maze_model, stored_contours)

            # open raw video and move to stim start frame
            if trial_mode:
                cap = cv2.VideoCapture(get_video_path_give_recuid(row['rec_uid']))
                if not cap.isOpened():
                    raise FileNotFoundError
                else:
                    if trial_mode: cap.set(1, row['stim_frame'])
                    else: 
                        cap.set(1, start_frame)


            # LOOP OVER FRAMES
            trial_stored_contours = []
            prev_frame_bl = 0  # keep track of the body length at each frame to remove jumps
            snout_position = None
            for frame in tqdm(np.arange(tot_frames)):  # loop over each frame and draw
                background = trial_background.copy()

                # Get body ellipse
                try:
                    centre = (int(np.mean([body_ellipse[frame, 0, 0], body_ellipse[frame, 0, 1]])),
                                int(np.mean([body_ellipse[frame, 1, 0], body_ellipse[frame, 1, 1]])))
                except:
                    continue

                main_axis = int(calc_distance_between_points_2d(body_ellipse[frame, :2, 0], body_ellipse[frame, :2, 1]))
                if main_axis > 100: main_axis = 15
                elif main_axis < 15: main_axis = 15
                if prev_frame_bl:
                    if abs(prev_frame_bl - main_axis) > prev_frame_bl*3:main_axis = prev_frame_bl
                prev_frame_bl = main_axis
                min_axis = int(main_axis*.3)
                angle = angle_between_points_2d_clockwise(body_ellipse[frame, :2, 0], body_ellipse[frame, :2, 1])

                # Draw the body ellipse
                cv2.ellipse(background, centre, (min_axis, main_axis), angle-90, 0, 360, (0, 255, 0), -1)
                cv2.ellipse(background, centre, (min_axis, main_axis), angle-90, 0, 360, (50, 50, 50), 2)

                # Draw current trial head contours
                coords = body_contour[frame, :2, :].T.astype(np.int32)
                head = head_contour[frame, :2, :].T.astype(np.int32)
                head_length = calc_distance_between_points_2d(head[0], head[1])
                if head_length > 15 and snout_position is not None:
                    head[1] = snout_position
                else:
                    snout_position = head[1]
                self.draw_contours(background, [head],  (0, 0, 255), (50, 50, 50))

                # flip frame Y
                background = np.array(background[::-1, :, :])

                # Put frame title
                if trial_mode:
                    ttl = frame_title + ' - Trial: {}'.format(row['trial_id'])
                else:
                    ttl = frame_title
                cv2.putText(background, ttl,
                            (int(maze_model.shape[1]/10),
                            int(maze_model.shape[1]/10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 1,
                            (255, 255, 255), 2, cv2.LINE_AA)

                # Time elapsed
                elapsed = frame / fps
                cv2.putText(background, str(round(elapsed, 2)),
                            (int(maze_model.shape[0]*.85),
                            int(maze_model.shape[1]*.8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.6,
                            (255, 255, 255), 2, cv2.LINE_AA)

                # Escape and Origin Arms
                if trial_mode:
                    cv2.putText(background, 'origin arm: ' + row['origin'],
                                (int(maze_model.shape[0]*.1),
                                int(maze_model.shape[1]*.15)),
                                cv2.FONT_HERSHEY_SIMPLEX, 1,
                                (255, 255, 255), 2, cv2.LINE_AA)
                    cv2.putText(background, 'escape arm: ' + row['escape'],
                                (int(maze_model.shape[0]*.1),
                                int(maze_model.shape[1]*.2)),
                                cv2.FONT_HERSHEY_SIMPLEX, 1,
                                (255, 255, 255), 2, cv2.LINE_AA)

                    # cv2.putText(background, 'is escape: ' + row['is_escape'],
                    #             (int(maze_model.shape[0]*.6),
                    #              int(maze_model.shape[1]*.15)),
                    #             cv2.FONT_HERSHEY_SIMPLEX, 1,
                    #             (255, 255, 255), 2, cv2.LINE_AA)

                # Head and body angle dials
                cc = (int(maze_model.shape[0]*.66), int(maze_model.shape[1]*.88))
                cv2.circle(background, cc, 100, (255, 255, 255), 2)
                cv2.ellipse(background, cc, (100, 5), - body_angle[frame], -45, 45, (0, 255, 0), -1)
                cv2.ellipse(background, cc, (50, 10), - head_angle[frame], -45, 45, (0, 0, 255), -1)
                cv2.ellipse(background, cc, (100, 2), - head_angle[frame] - (-body_angle[frame]) - 90, -45, 45, (255, 255, 255), -1)

                # threat frame
                if trial_mode:
                    threat = background[threat_cropping[0][0]:threat_cropping[0][1],
                                        threat_cropping[1][0]:threat_cropping[1][1]]
                    threat = cv2.resize(threat, (background.shape[1], background.shape[0]))

                    # video frame
                    ret, videoframe = cap.read()
                    if not ret:
                        raise ValueError

                    wh_ratio = videoframe.shape[0] / videoframe.shape[1]
                    height = 350
                    width = int(250*wh_ratio)
                    videoframe = cv2.resize(videoframe, (height, width))

                    # Create the whole frame
                    shape = background.shape
                    whole_frame = np.zeros((shape[0], shape[1]*2, shape[2])).astype(np.uint8)
                    whole_frame[:, :shape[0], :] = background
                    whole_frame[:, shape[0]:, :] = threat
                    whole_frame[shape[0]-width:, :height, :] = videoframe
                else:
                    whole_frame = background.copy()

                # Show and write
                # cv2.imshow("frame", whole_frame)
                # cv2.waitKey(1)
                writer.write(whole_frame)

                # Store contours points of this trials to use them as background for next
                trial_stored_contours.append(coords)

                # add frame's contour to trial background
                mask = np.uint8(np.ones(trial_background.shape) * 0)
                self.draw_contours(mask, [trial_stored_contours[-1]],  (255, 255, 255), None)
                mask = mask.astype(bool)
                trial_background[mask] = trial_background[mask] * .9
 

            stored_contours.append(trial_stored_contours)
        writer.release()





    """
    #####################################################################################################################################################################################################################################################
    #####################################################################################################################################################################################################################################################
    #####################################################################################################################################################################################################################################################
    """

    def prepare_background(self, n, maze_model, stored_contours):
        if n == 0:
            trial_background = maze_model.copy()
        else:
            trial_background = maze_model.copy()
            if stored_contours:
                for past_trial in stored_contours:
                    mask = np.uint8(np.ones(trial_background.shape) * 0)
                    self.draw_contours(mask, past_trial,  (255, 255, 255), None)
                    mask = mask.astype(bool)
                    trial_background[mask] = trial_background[mask] * .8

        return trial_background


    @staticmethod
    def draw_contours(fr, cont, c1, c2):
        if c2 is not None:
            cv2.drawContours(fr, cont, -1, c2, 4)
        cv2.drawContours(fr, cont, -1, c1, -1)    





if __name__ == "__main__":        
    videomaker = VideoMaker()

    videomaker.first_trial()


    plt.show()
















