
import sys
sys.path.append('./')

from Utilities.Maths.math_utils import *
from Processing.tracking_stats.extract_velocities_from_tracking import complete_bp_with_velocity, get_body_segment_stats
from Processing.rois_toolbox.rois_stats import get_roi_at_each_frame
from Utilities.file_io.files_load_save import load_yaml
try:
    from Processing.trials_analysis.vte_analysis import VTE
except:
    pass

import warnings
import cv2
import numpy as np
from collections import namedtuple
import os
import pandas as pd
from nptdms import TdmsFile
from database.dj_config import start_connection
try:
    import datajoint as dj
except:
    pass
else:
    from database.TablesPopulateFuncs import *

    dbname, _ = start_connection()

    schema = dj.schema(dbname, locals())


    @schema
    class Mice(dj.Manual):
        definition = """
            # Mouse table lists all the mice used and the relevant attributes
            mouse_id: varchar(128)                        # unique mouse id
            ---
            strain:   varchar(128)                        # genetic strain
            dob: varchar(128)                             # mouse date of birth 
            sex: enum('M', 'F', 'U')                      # sex of mouse - Male, Female, or Unknown/Unclassified
            single_housed: enum('Y', 'N')                 # single housed or group caged
            enriched_cage: enum('Y', 'N')                 # presence of wheel or other stuff in the cage
        """

    @schema
    class Experiments(dj.Manual):
        definition = """
        # Name of the experiments and location of components templates
        experiment_name: varchar(128)
        ---
        templates_folder: varchar(256)
        """

    @schema
    class Sessions(dj.Manual):
        definition = """
        # A session is one behavioural experiment performed on one mouse on one day
        uid: smallint     # unique number that defines each session
        session_name: varchar(128)  # unique name that defines each session - YYMMDD_MOUSEID
        ---
        -> Mice
        date: date             # date in the YYYY-MM-DD format
        experiment_name: varchar(128)  # name of the experiment the session is part of 
        -> Experiments      # ame of the experiment
        """

    @schema
    class CommonCoordinateMatrices(dj.Computed):
        definition = """
            # Stores matrixes used to align video and tracking data to standard maze model
            -> Sessions
            ---
            maze_model: longblob   # 2d array with image used for correction
            correction_matrix: longblob  # 2x3 Matrix used for correction
            alignment_points: longblob     # array of X,Y coords of points used for affine transform
            top_pad: int            # y-shift
            side_pad: int            # x-shift
        """

        def make(self, key):
            make_commoncoordinatematrices_table(self, key, Sessions, VideoFiles)

    @schema
    class Templates(dj.Imported):
        definition = """
        # stores the position of each maze template for one experiment
        -> Sessions
        ---
        s: longblob  # Shelter platform template position
        t: longblob  # Threat platform
        p1: longblob  # Other platforms
        p2: longblob
        p3: longblob
        p4: longblob
        p5: longblob
        p6: longblob
        b1: longblob  # Bridges
        b2: longblob
        b3: longblob
        b4: longblob
        b5: longblob
        b6: longblob
        b7: longblob
        b8: longblob
        b9: longblob
        b10: longblob
        b11: longblob
        b12: longblob
        b13: longblob
        b14: longblob
        b15: longblob
        """

        def make(self, key):
            new_key = make_templates_table(key, Sessions, CommonCoordinateMatrices)
            if new_key is not None:
                print('Populating templates for session ', key['uid'])
                self.insert1(new_key)


    #!  ########################################################################################################################################################################################################################################################################################################################################################
    #!  ########################################################################################################################################################################################################################################################################################################################################################
    #!  ########################################################################################################################################################################################################################################################################################################################################################



    @schema
    class Recordings(dj.Imported):
        definition = """
            # Within one session one may perform several recordings. Each recording has its own video and metadata files
            recording_uid: varchar(128)   # uniquely identifying name for each recording YYMMDD_MOUSEID_RECNUM
            -> Sessions
            ---
            software: enum('behaviour', 'mantis')
            ai_file_path: varchar(256)    # path to mantis .tdms file with analog inputs and stims infos
        """
        class AnalogInputs(dj.Part):
            definition = """
                # Stores data from relevant AI channels recorded with NI board
                -> Recordings
                ---
                tstart: float                           # t0 from mantis manuals .tdms
                overview_camera_triggers: longblob      # Frame triggers signals efferent copy
                threat_camera_triggers: longblob        # a
                audio_irled: longblob                   # HIGH when auditory stimulus being produced
                audio_signal: longblob                  # voltage from amplifier to speaker
                manuals_names: longblob                 # list of strings of name of manual protocols
                manuals_timestamps: longblob            # list of floats of timestamps of manual protocols
                ldr: longblob                           # light dependant resistor signal
            """

        def print(self):
            print(self.AnalogInputs.heading)
            for line in self.AnalogInputs.fetch():
                print('tule', line)


        def make(self, key):
            make_recording_table(self, key)

    @schema
    class VideoFiles(dj.Imported):
        definition = """
            # stores paths to video files and all metadata and posedata
            -> Recordings
            camera_name: enum('overview', 'threat', 'catwalk', 'top_mirror', 'side_mirror')       # name of the camera
            ---
            video_filepath: varchar(256)          # path to the videofile
            converted_filepath: varchar(256)      # path to converted .mp4 video, if any, else is same as video filepath    
            metadata_filepath: varchar(256)       # if acquired with mantis a .tdms metadata file was produced, path ot it.
            pose_filepath: varchar(256)           # path to .h5 pose file
            """

        class Metadata(dj.Part):
            definition = """
                # contains info about each video
                -> VideoFiles
                ---
                fps: int                        # fps
                tot_frames: int
                frame_width: int
                frame_height: int
                frame_size: int                 # number of bytes for the whole frame
                camera_offset_x: int            # camera offset
                camera_offset_y: int            # camera offset
            """

        def make(self, key):
            make_videofiles_table(self, key, Recordings)

    #!  ########################################################################################################################################################################################################################################################################################################################################################
    #!  ########################################################################################################################################################################################################################################################################################################################################################
    #!  ########################################################################################################################################################################################################################################################################################################################################################

    @schema
    class BehaviourStimuli(dj.Computed):
        definition = """
        # Stimuli of sessions recorded with old behaviour software
        -> Recordings
        stimulus_uid: varchar(128)  # uniquely identifying ID for each trial YYMMDD_MOUSEID_RECNUM_TRIALNUM
        ---
        stim_type: varchar(128)
        stim_start: int                 # number of frame at start of stim
        stim_duration: int              # duration in frames
        stim_name: varchar(128)         # list of other stuff ? 
        video: varchar(256)             # name of corresponding video
        """

        def make(self, key):
            make_behaviourstimuli_table(self, key, Recordings, VideoFiles)


    @schema 
    class MantisStimuli(dj.Computed):
        definition = """
            # stores metadata regarding stimuli with Mantis software
            -> Recordings
            stimulus_uid:       varchar(128)      # uniquely identifying ID for each trial YYMMDD_MOUSEID_RECNUM_TRIALNUM
            ---
            overview_frame:     int             # frame number in overview camera (of onset)
            overview_frame_off: int
            duration:           float                   # duration in seconds
            stim_type:          varchar(128)         # audio vs visual
            stim_name:          varchar(128)         # name 
        """

        class VisualStimuliLogFile(dj.Part):
            definition = """
                -> MantisStimuli
                ---
                filepath:       varchar(128)
            """

        def make(self, key):
            make_mantistimuli_table(self, key, Recordings, VideoFiles)    


    
    @schema
    class VisualStimuliMetadata(dj.Imported):
        definition = """
            -> MantisStimuli
            ---
            stim_type:              varchar(128)    # loom, grating...
            modality:               varchar(128)    # linear, exponential. 
            params_file:            varchar(128)    # name of the .yml file with the params
            time:                   varchar(128)    # time at which the stim was delivered
            units:                  varchar(128)    # are the params defined in degrees, cm ...
    
            start_size:             float       
            end_size:               float
            expansion_time:         float
            on_time:                float
            off_time:               float
    
            color:                  float
            backgroun_color:        float
            contrast:               float
    
            position:               blob
            repeats:                int
            sequence_number:        float           # sequential stim number in the session
         """
    
        def make(self, key):
            make_visual_stimuli_metadata_table(self, key, MantisStimuli)

    #!  ########################################################################################################################################################################################################################################################################################################################################################
    #!  ########################################################################################################################################################################################################################################################################################################################################################
    #!  ########################################################################################################################################################################################################################################################################################################################################################

    @schema
    class TrackingData(dj.Computed):
        definition = """
            # store dlc data for bodyparts and body segments
            -> VideoFiles
        """

        class BodyPartData(dj.Part):
            definition = """
                # stores X,Y,Velocity... for a single bodypart
                -> TrackingData
                bpname: varchar(128)        # name of the bodypart
                ---
                tracking_data: longblob     # pandas dataframe with X,Y,Velocity, MazeComponent ... 
            """

        def make(self, key):
            make_trackingdata_table(self, key, VideoFiles, CommonCoordinateMatrices, Templates, Sessions, fast_mode=False)

    @schema
    class BehaviourTrialOutcomes(dj.Manual):
        definition = """
            # For each stimulus stores info about the escape...
            stimulus_uid: varchar(128)          # name of the stimulus
            ---
            criteria: varchar(128)              # e.g. if a time limit is set to specify if a trial is escape or not
            threshold: int                      # the value associated to the criteria (e.g. num of seconds)
            escape: enum('true', 'false')
            origin_arm: varchar(128)
            escape_arm: varchar(128)
            x_y_theta: longblob                # x,y position and body orientation at stimulus onset
            reaction_time: int                 # reaction time, if calculated
            time_to_shelter: int               # number of seconds before the shelter is reached 
        """

    @schema
    class DLCmodels(dj.Lookup):
        definition = """
            # It got pointers to dlc models so that they can be used for analysing videos
            model_name: varchar(256)                        # name given to the model
            camera: enum('overview', 'threat', 'mirrors', 'overview_mantis')   # for which kind of video it can be used
            ---
            cfg_file_path: varchar(256)                     # path to the cfg.yml file
            iteration: int
        """

        def populate(self):
            make_dlcmodels_table(self)


    @schema
    class AllExplorations(dj.Manual):
        definition = """
            exploration_id: int
            ---
            session_uid: int
            experiment_name: varchar(128)
            tracking_data: longblob
            total_travel: float               # Total distance covered by the mouse
            tot_time_in_shelter: float        # Number of seconds spent in the shelter
            tot_time_on_threat: float         # Number of seconds spent on threat platf
            duration: float                   # Total duration of the exploration in seconds
            median_vel: float                  # median velocity in px/s 
            session_number_trials: int      # Number of trials in the session following the expl
            exploration_start: int              # frame start exploration
        """


    @schema
    class AllTrials(dj.Manual):
        definition = """
            trial_id: int
            ---
            session_uid: int
            recording_uid: varchar(128)
            experiment_name: varchar(128)
            tracking_data: longblob
            stim_frame: int
            stim_type: enum('audio', 'visual')
            stim_duration: int

            number_of_trials: int
            trial_number: int

            is_escape: enum('true', 'false')
            escape_arm: enum('Left_Far', 'Left_Medium', 'Centre', 'Right_Medium', 'Right_Far', 'Right2', 'Left2', 'nan') 
            origin_arm:  enum('Left_Far', 'Left_Medium', 'Centre', 'Right_Medium', 'Right_Far', 'Right2', 'Left2', 'nan')         
            time_out_of_t: float
            fps: int
            escape_duration: int        # duration in seconds

            threat_exits: longblob
        """



if __name__ == "__main__":
    # VideoTdmsMetadata().drop()
    print(VisualStimuliMetadata())