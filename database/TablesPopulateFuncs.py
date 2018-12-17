import sys
sys.path.append('./')

import time
import datajoint as dj
from database.dj_config import start_connection
from nptdms import TdmsFile
import pandas as pd
import os
from collections import namedtuple
import numpy as np
import cv2
import warnings
import matplotlib.pyplot as plt

from Utilities.file_io.files_load_save import load_yaml, load_tdms_from_winstore
from Utilities.video_and_plotting.commoncoordinatebehaviour import run as get_matrix
from database.NewTablesDefinitions import *
from Utilities.video_and_plotting.video_editing import Editor


""" 
    Collection of functions used to populate the dj.Import and dj.Compute
    tables defined in NewTablesDefinitions.py

    CommonCoordinateMatrices    ok
    Templates                   ok
    Recordings                  ok
    VideoFiles                  ok
    IncompleteVideoFiles        ok
    BehaviourStimuli            ok
    MantisStimuli
    TrackingData
"""

class ToolBox:
    def __init__(self):
        # Load paths to data folders
        self.paths = load_yaml('paths.yml')
        self.raw_video_folder = os.path.join(
            self.paths['raw_data_folder'], self.paths['raw_video_folder'])
        self.raw_metadata_folder = os.path.join(
            self.paths['raw_data_folder'], self.paths['raw_metadata_folder'])
        self.tracked_data_folder = self.paths['tracked_data_folder']
        self.analog_input_folder = os.path.join(self.paths['raw_data_folder'], 
                                                self.paths['raw_analoginput_folder'])
        self.pose_folder = self.paths['tracked_data_folder']

    def get_behaviour_recording_files(self, session):
        raw_video_folder = self.raw_video_folder
        raw_metadata_folder = self.raw_metadata_folder

        # get video and metadata files
        videos = sorted([f for f in os.listdir(raw_video_folder)
                            if session['session_name'].lower() in f.lower() and 'test' not in f
                            and '.h5' not in f and '.pickle' not in f])
        metadatas = sorted([f for f in os.listdir(raw_metadata_folder)
                            if session['session_name'].lower() in f.lower() and 'test' not in f and '.tdms' in f])

        if videos is None or metadatas is None:
            raise FileNotFoundError(videos, metadatas)

        # Make sure we got the correct number of files, otherwise ask for user input
        if not videos or not metadatas:
            if not videos and not metadatas:
                print('Couldnt find filessss')
                return None, None
                # raise ValueError('Found no files for ', session['session_name'])
            print('couldnt find files for session: ',
                    session['session_name'])
            raise FileNotFoundError('dang')
        else:
            if len(videos) != len(metadatas):
                print('Found {} videos files: {}'.format(len(videos), videos))
                print('Found {} metadatas files: {}'.format(
                    len(metadatas), metadatas))
                raise ValueError(
                    'Something went wront wrong trying to get the files')

            num_recs = len(videos)
            print(' ... found {} recs'.format(num_recs))
            return videos, metadatas


    def open_temp_tdms_as_df(self, path, move=True):
        """open_temp_tdms_as_df [gets a file from winstore, opens it and returns the dataframe]
        
        Arguments:
            path {[str]} -- [path to a .tdms]
        """
        # Download .tdms from winstore, and open as a DataFrame
        # ? download from winstore first and then open, faster?
        if move:
            temp_file = load_tdms_from_winstore(path)
        else:
            temp_file = path

        print('opening ', temp_file, ' with size {} bytes'.format(
            round(os.path.getsize(temp_file)/1000000000, 2)))
        bfile = open(temp_file, 'rb')
        tdmsfile = TdmsFile(bfile, memmap_dir="M:\\")
        print('     ... opened')
        tdms_df = tdmsfile.as_dataframe()
        print('         ... as dataframe')
        # Extract data and insert in key
        cols = list(tdms_df.columns)
        return tdms_df, cols

    def extract_behaviour_stimuli(self, aifile):
        """extract_behaviour_stimuli [given the path to a .tdms file with session metadata extract
        stim names and timestamp (in frames)]
        
        Arguments:
            aifile {[str]} -- [path to .tdms file] 
        """
        # Get .tdms as a dataframe
        tdms_df, cols = self.open_temp_tdms_as_df(aifile, move=False)
        # ? Print out content of the dataframe
        # with open('behav_cols.txt', 'w+') as out:
        #     for c in cols:
        #         out.write(c+'\n\n')

        # Loop over the dataframe columns named like : 
        # /'Visual Stimulis'/' 20130-FC_slowloom'
        stim_cols = [c for c in cols if 'Stimulis' in c]
        stimuli = []
        stim = namedtuple('stim', 'type name frame')
        for c in stim_cols:
            stim_type = c.split(' Stimulis')[0][2:].lower()
            if 'digit' in stim_type: continue
            stim_name = c.split('-')[-1][:-2].lower()
            stim_frame = int(c.split("'/' ")[-1].split('-')[0])
            stimuli.append(stim(stim_type, stim_name, stim_frame))
        return stimuli

    def extract_ai_info(self, key, aifile):
        """
        aifile: str path to ai.tdms

        extract channels values from file and returns a key dict for dj table insertion

        """

        # Get .tdms as a dataframe
        tdms_df, cols = self.open_temp_tdms_as_df(aifile, move=True)
        chs = ["/'OverviewCameraTrigger_AI'/'0'", "/'ThreatCameraTrigger_AI'/'0'", "/'AudioIRLED_AI'/'0'", "/'AudioFromSpeaker_AI'/'0'"]

        print('Ready to extract channels info')
        # Get the channels we care about
        key['overview_camera_triggers'] = np.round(tdms_df["/'OverviewCameraTrigger_AI'/'0'"].values, 2)
        key['threat_camera_triggers'] = np.round(tdms_df["/'ThreatCameraTrigger_AI'/'0'"].values, 2)
        key['audio_irled'] = np.round(tdms_df["/'AudioIRLED_AI'/'0'"].values, 2)
        if "/'AudioFromSpeaker_AI'/'0'" in cols:
            key['audio_signal'] = np.round(tdms_df["/'AudioFromSpeaker_AI'/'0'"].values, 2)
        else:
            key['audio_signal'] = -1
        key['ldr'] = -1  # ? insert here

        # Extract manual timestamps and add to key
        names, times = [], []
        for c in cols:
            if c in chs: continue
            elif 't0' in c:
                key['tstart'] = float(c.split("'/'")[-1][:-2])
            else:
                names.append(c.split("'/'")[0][2:])
                times.append(float(c.split("'/'")[-1][:-2]))
        key['manuals_names'] = -1
        # warnings.warn('List of strings not currently supported, cant insert manuals names')
        key['manuals_timestamps'] = np.array(times)
        [print('\n\n',k,'\n', v) for k,v in key.items()]
        return key

""" 
##################################################

##################################################
"""

def make_commoncoordinatematrices_table(key):
    """make_commoncoordinatematrices_table [Allows user to align frame to model
    and stores transform matrix for future use]
    
    Arguments:
        key {[dict]} -- [key attribute of table autopopulate method from dj]
    """

    # Get the maze model template
    maze_model = cv2.imread('Utilities\\video_and_plotting\\mazemodel.png')
    maze_model = cv2.resize(maze_model, (1000, 1000))
    maze_model = cv2.cv2.cvtColor(maze_model, cv2.COLOR_RGB2GRAY)

    # Get path to video of first recording
    rec = [r for r in VideoFiles if r['session_name']
            == key['session_name'] and r['camera_name']=='overview']

    if not rec:
        raise ValueError(
            'Did not find recording while populating CCM table. Populate recordings first! Session: ', key['session_name'])
    else:
        videopath = rec[0]

    # Apply the transorm [Call function that prepares data to feed to Philip's function]
    """ 
        The correction code is from here: https://github.com/BrancoLab/Common-Coordinate-Behaviour
    """
    matrix, points = get_matrix(videopath, maze_model=maze_model)

    # Return the updated key
    key['maze_model'] = maze_model
    key['correction_matrix'] = matrix
    key['alignment_points'] = points
    return key


def make_templates_table(key):
    """[allows user to define ROIs on the standard maze model that match the ROIs]
        """

    # Get all possible components name
    nplatf, nbridges = 6, 15
    platforms = ['p'+str(i) for i in range(1, nplatf + 1)]
    bridges = ['b'+str(i) for i in range(1, nbridges + 1)]
    components = ['s', 't']
    components.extend(platforms)
    components.extend(bridges)

    # Get maze model
    mmc = [m for m in CommonCoordinateMatrices if m['uid'] == key['uid']]
    if not mmc:
        raise ValueError(
            'Could not find CommonCoordinateBehaviour Matrix for this entry: ', key)
    else:
        model = mmc[0]['maze_model']

    # Load yaml with rois coordinates
    paths = load_yaml('paths.yml')
    rois = load_yaml(paths['maze_model_templates'])

    # return new key
    return {**key, **rois}


def make_recording_table(table, key):
    def behaviour(table, key, software):
        tb = ToolBox()
        videos, metadatas = tb.get_behaviour_recording_files(key)
        if videos is None: return
        # Loop over the files for each recording and extract info
        for rec_num, (vid, met) in enumerate(zip(videos, metadatas)):
            if vid.split('.')[0].lower() != met.split('.')[0].lower():
                raise ValueError('Files dont match!', vid, met)

            name = vid.split('.')[0]
            try:
                recnum = int(name.split('_')[2])
            except:
                recnum = 1

            if rec_num+1 != recnum:
                raise ValueError(
                    'Something went wrong while getting recording number within the session')

            rec_name = key['session_name']+'_'+str(recnum)
            
            # Insert into table
            rec_key = key.copy()
            rec_key['recording_uid'] = rec_name
            rec_key['ai_file_path'] = os.path.join(tb.raw_metadata_folder, met)
            rec_key['software'] = software
            table.insert1(rec_key)

    def mantis(table, key, software):
        # Get AI file and insert in Recordings table
        tb = ToolBox()
        rec_name = key['session_name']
        aifile = [os.path.join(tb.analog_input_folder, f) for f 
                    in os.listdir(tb.analog_input_folder) 
                    if rec_name in f]
        if not aifile:
            print('aifile not found for session: ', key)
            return
        else:
            aifile = aifile[0]
        
        key_copy = key.copy()
        key_copy['recording_uid'] = rec_name
        key_copy['software'] = software
        key_copy['ai_file_path'] = aifile
        table.insert1(key_copy)

        # Extract info from aifile and populate part table
        ai_key = tb.extract_ai_info(key, aifile)
        ai_key['recording_uid'] = rec_name

        print('Key of size: ', sys.getsizeof(ai_key))
        table.AnalogInputs.insert1(ai_key)
        
        print('Succesfully inserted into mantis table')

    # See which software was used and call corresponding function
    print(' Processing: ', key)
    if key['uid'] < 184:
        software = 'behaviour'
        behaviour(table, key, software)
    else:
        software = 'mantis'
        mantis(table, key, software)


def make_videofiles_table(table, key, recordings, videosincomplete):
    def make_videometadata_table(filepath, key):
        # Get videometadata
        cap = cv2.VideoCapture(filepath)
        key['tot_frames'], fps, key['frame_height'], key['fps'] = Editor.get_video_params(
            cap)
        key['frame_width'] = np.int(fps)
        key['frame_size'] =  key['frame_width']* key['frame_height']
        key['camera_offset_x'], key['camera_offset_y'] = -1, -1
        return key

    def behaviour(table, key, videosincomplete):
        tb  = ToolBox()
        videos, metadatas = tb.get_behaviour_recording_files(key)
        
        if key['recording_uid'].count('_') == 1:
            recnum = 1
        else:
            rec_num = int(key['recording_uid'].split('_')[-1])
        rec_name = key['recording_uid']
        try:
            vid, met = videos[rec_num-1], metadatas[rec_num-1]
            vid, met = os.path.join(tb.raw_video_folder, vid), os.path.join(tb.raw_metadata_folder, vid)
        except:
            raise ValueError('Could not collect video and metadata files:' , rec_num-1, rec_name, videos)
        # Get deeplabcut data
        posefile = [os.path.join(tb.tracked_data_folder, f) for f in os.listdir(tb.tracked_data_folder)
                    if rec_name == os.path.splitext(f)[0].split('_pose')[0] and '.pickle' not in f]
        
        if not posefile:
            new_rec_name = rec_name[:-2]
            posefile = [os.path.join(tb.tracked_data_folder, f) for f in os.listdir(tb.tracked_data_folder)
                        if new_rec_name == os.path.splitext(f)[0].split('_pose')[0] and '.pickle' not in f]

        if not posefile:
            # ! pose file was not found, create entry in incompletevideos table to mark we need dlc analysis on this
            incomplete_key = key.copy()
            incomplete_key['camera_name'] = 'overview'
            incomplete_key['conversion_needed'] = 'false'
            incomplete_key['dlc_needed'] = 'true'
            try:
                videosincomplete.insert1(incomplete_key)
            except:
                print(videosincomplete.describe())
                raise ValueError('Could not insert: ', incomplete_key )

            # ? Create dummy posefile name which will be replaced with real one in the future
            vid_name, ext = vid.split('.')
            posefile = vid_name+'_pose'+ext

        elif len(posefile) > 1:
            raise FileNotFoundError('Found too many pose files: ', posefile)
        else:
            posefile = posefile[0]

        # Insert into Recordings.VideoFiles 
        new_key = key.copy()
        new_key['camera_name'] = 'overview'
        new_key['video_filepath'] = vid
        new_key['converted_filepath'] = 'nan'
        new_key['metadata_filepath'] = 'nan'
        new_key['pose_filepath'] = posefile
        table.insert1(new_key)

        return vid

    def mantis(table, key, videosincomplete):
        def insert_for_mantis(table, key, camera, vid, conv, met, pose):
            to_remove = ['tot_frames', 'frame_height', 'frame_width', 'frame_size',
                        'camera_offset_x', 'camera_offset_y', 'fps']
            
            video_key = key.copy()
            video_key['camera_name'] = camera
            video_key['video_filepath'] = vid
            video_key['converted_filepath'] = conv
            video_key['metadata_filepath'] = met
            video_key['pose_filepath'] = pose
            if 'conversion_needed' in video_key.keys():
                del video_key['conversion_needed'], video_key['dlc_needed']
            try:
                kk = tuple(video_key.keys())
                for n in to_remove:
                    if n in kk: del video_key[n]
                table.insert1(video_key)
            except:
                raise ValueError('Could not isnert ', video_key)
            metadata_key = make_videometadata_table(video_key['converted_filepath'], key)
            if 'conversion_needed' in metadata_key.keys():
                del metadata_key['conversion_needed'], metadata_key['dlc_needed']
            try:
                table.Metadata.insert1(metadata_key)
            except:
                return
            
        def check_files_correct(ls, name):
            """check_files_correct [check if we found the expected number of files]
            
            Arguments:
                ls {[list]} -- [list of file names]
                name {[str]} -- [name of the type of file we are looking for ]
            
            Raises:
                FileNotFoundError -- [description]
            
            Returns:
                [bool] -- [return true if everuything is fine else is false]
            """

            if not ls:
                print('Did not find ', name)
                return False
            elif len(ls)>1:
                raise FileNotFoundError('Found too many ', name, ls)
            else:
                return True

        def add_videosincomplete_entry(videosincomplete, ikey, vid, converted_check, pose_check):
            """add_videosincomplete_entry [adds entry to videos incompelte table to mark that stuff needs to be done ]
            
            Arguments:
                videosincomplete {[obj]} -- [dj table]
                key {[dict]} -- [key]
                vid {[str]} -- [name of video]
                converted_check {[bool]} -- [conversion needed]
                pose_check {[bool]} -- [dlc eneeded]
            """

            tokeep = ['recording_uid', 'uid', 'session_name']
            kk = tuple(ikey.keys())
            for k in kk:
                if k not in tokeep: del ikey[k]

            cameras = ['overview', 'threat', 'catwalk', 'top_mirror', 'side_mirror']
            camera = [c for c in cameras if c in vid.lower()]
            if not camera:
                raise ValueError('sometihngs wrong ', vid)
            else:
                camera = camera[0]
            key['camera_name'] = camera
            if converted_check:
                ikey['conversion_needed'] = 'false'
            else:
                ikey['conversion_needed'] = 'true'
            if pose_check:
                ikey['dlc_needed'] = 'false'
            else:
                ikey['dlc_needed'] = 'true'
            try:
                videosincomplete.insert1(ikey)
            except:
                raise ValueError('Could not insert ', ikey, 'in', videosincomplete.heading)

        #############################################################################################

        tb = ToolBox()  # toolbox

        # Get video Files
        videos = [f for f in os.listdir(tb.raw_video_folder)
                        if 'tdms' in f and key['session_name'] in f]
        
        # Loop and get matching files
        for vid in videos:
            # Get videos
            videoname, ext = vid.split('.')
            converted = [f for f in os.listdir(tb.raw_video_folder)
                        if videoname in f and '__joined' in f]
            converted_check = check_files_correct(converted, 'converted')

            metadata = [f for f in os.listdir(tb.raw_metadata_folder)
                        if videoname in f and 'tdms' in f]
            metadata_check = check_files_correct(metadata, 'metadata')

            posedata = [os.path.splitext(f)[0].split('_pose')[0]+'.h5' 
                        for f in os.listdir(tb.pose_folder)
                        if videoname in f and 'h5' in f]
            pose_check = check_files_correct(posedata, 'pose data')
            
            # Check if anything is missing
            if not metadata_check: raise FileNotFoundError('Could not find metadata file!!')
            if not converted_check or not pose_check:
                add_videosincomplete_entry(videosincomplete, key, vid, converted_check, pose_check)
                # ? add dummy files names which will be replaced with real ones in the future
                if not converted_check:
                    converted = videoname+'__joined'+ext
                if not pose_check:
                    posedata = videoname+'_pose.h5'

            # Get Camera Name and views videos
            if 'Overview' in vid:
                camera = 'overview'
            elif 'Threat' in vid:
                camera = 'threat'

                # ? work on views videos
                # Get file names and create cropped videos if dont exist
                ed = Editor()
                catwalk, side, top = ed.mirros_cropper(os.path.join(tb.raw_video_folder,vid),
                                                            os.path.join(tb.raw_video_folder, 'Mirrors'))
                views_videos = [catwalk, side, top]
                views_names = ['catwalk', 'side_mirror', 'top_mirror']
                # Get pose names
                views_poses = {}
                for vh, view_name in zip(views_videos, views_names):
                    n = os.path.split(vh)[-1].split('.')[0]
                    pd = [os.path.splitext(f)[0].split('_pose')[0]+'.h5'
                                for f in os.listdir(os.path.join(tb.pose_folder, 'Mirrors'))
                                if n in f and 'h5' in f]
                    
                    pd_check = check_files_correct(pd, 'cropped video pose file')
                    if not pd_check:  
                        add_videosincomplete_entry(videosincomplete, key, view_name, True, pd_check)
                        # ? add dummy file name 
                        pd = n+'_pose.h5'
                    else: pd = pd[0]
                    views_poses[view_name] = pd

                # Insert into table [video and converted are the same here]
                view = namedtuple('view', 'camera video metadata pose')
                views = [view('catwalk', catwalk, 'nan', views_poses['catwalk']),
                        view('side_mirror', side, 'nan', views_poses['side_mirror']),
                        view('top_mirror', top, 'nan', views_poses['top_mirror'])]
                for insert in views:
                    insert_for_mantis(table, key, insert.camera, insert.video,
                                        insert.video, insert.metadata, insert.pose)
            else:
                raise ValueError('Unexpected videoname ', vid)

            # Insert Main Video (threat or overview) in table
            insert_for_mantis(table, key, camera, os.path.join(tb.raw_video_folder, vid),
                                os.path.join(tb.raw_video_folder, converted[0]),
                                os.path.join(tb.raw_metadata_folder, metadata[0]),
                                os.path.join(tb.pose_folder, posedata[0]))

    #####################################################################################################################
    #####################################################################################################################
    #####################################################################################################################

    print('Processing:  ', key)
    # Call functions to handle insert in main table
    software = [r['software'] for r in recordings.fetch(as_dict=True) if r['recording_uid']==key['recording_uid']][0]
    if not software:
        raise ValueError()
    if software == 'behaviour':
        videopath = behaviour(table, key, videosincomplete)
        # Insert into part table
        metadata_key = make_videometadata_table(videopath, key)
        metadata_key['camera_name'] = 'overview'
        table.Metadata.insert1(metadata_key)
    else:
        videopath = mantis(table, key, videosincomplete)

    
def make_behaviourstimuli_table(table, key, recordings, videofiles):
    if key['uid'] > 184:
        print(key['recording_uid'], '  was not recorded with behaviour software')
        return
    else:
        print('Extracting stimuli info for recording: ', key['recording_uid'])

    # Get file paths    
    rec = [r for r in recordings.fetch(as_dict=True) if r['recording_uid']==key['recording_uid']][0]
    tdms_path = rec['ai_file_path']
    vid = [v for v in videofiles.fetch(as_dict=True) if v['recording_uid']==key['recording_uid']][0]
    videopath = vid['video_filepath']

    # Get stimuli
    tb = ToolBox()
    stimuli = tb.extract_behaviour_stimuli(tdms_path)

    # Add in table
    for i, stim in enumerate(stimuli):
        stim_key = key.copy()
        stim_key['stimulus_uid'] = key['recording_uid']+'_{}'.format(i)


        if 'audio' in stim.name: stim_key['stim_duration'] = 9 # ! hardcoded
        else: stim_key['stim_duration']  = 5
        
        stim_key['video'] = videopath
        stim_key['stim_type'] = stim.type
        stim_key['stim_start'] = stim.frame
        stim_key['stim_name'] = stim.name
        table.insert1(stim_key)



def make_mantistimuli_table(table, key, recordings):
    if key['uid'] <= 184:
        print(key['recording_uid'],
                '  was not recorded with mantis software')
        return
    else:
            print('Pop mantis stimuli for: ', key['recording_uid'])


    tb = ToolBox()
    rec = [r for r in recordings if r['recording_uid']==key['recording_uid']]
    aifile = rec['ai_file_path']

    # Get stimuli names from the ai file
    tdms_df, cols = tb.open_temp_tdms_as_df(aifile, move=True)

    # Get analog channel to use 
    if 'AudioFromSpeaker_AI' in cols:
        ch = 'AudioFromSpeaker_AI'
    else:
        ch = 'AudioIRLED_analog'

    # Get names of stimuli
    to_ignore = ['t0','AudioIRLED_analog']
    stim_names = [c.split("'/'")[0][2:] for c in cols if not [i for i in to_ignore if i in c]]


    # Get stim times from channel data
    plt.plot(ch)
    plt.plot(np.diff(ch))
    plt.show()






