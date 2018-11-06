from Tables_definitions import *

import datajoint as dj
import os
import pyexcel
import yaml
import moviepy
import cv2
from moviepy.editor import VideoFileClip
from shutil import copyfile

from utils.video_editing import *


class PopulateDatabase:
    def __init__(self):
        """
        Collection of methods to populate the different


        """
        print("""
        Ready to populate database. Available classes:
                * Mouse
                * Experiment
                * Surgery
                * Manipulation
                * Session
            Updating SESSION will also update:
                * NeuralRecording
                * BehaviourRecording
                * BehaviourTrial""")

        # Hard coded paths to relevant files and folders
        paths = yaml.load('database/data_paths.yml')


        self.mice_records = paths['mice_records']
        self.exp_records = paths['exp_records']

        self.raw_data_folder = paths['mice_records']
        self.raw_to_sort = os.path.jioin(self.raw_data_folder, paths['to_sort'])
        self.raw_metadata_folder = os.path.join(self.raw_data_folder, paths['metadata'])
        self.raw_video_folder = os.path.join(self.raw_data_folder, paths['video'])

        self.trials_clips = os.path.join(self.raw_data_folder, paths['trials_clips'])
        self.tracked_data_folder = paths['tracked_data_folder']

    @staticmethod
    def mouse(filepath):
        print(" Update MOUSE table from excel file.")
        print(""" 
        Table definition:
            {}""".format(Mouse.definition))

    @staticmethod
    def experiment(filepath):
        print(" Update EXPERIMENT table from excel file.")
        print(""" 
        Table definition:
            {}""".format(Experiment.definition))

    @staticmethod
    def surgery(filepath):
        print(" Update SURGERY table from excel file.")
        print(""" 
        Table definition:
            {}""".format(Surgery.definition))

    @staticmethod
    def manipulation(filepath):
        print(" Update MANIPULATION table from excel file.")
        print(""" 
        Table definition:
            {}""".format(Manipulation.definition))

    @staticmethod
    def session(filepath):
        print(" Update SESSION table from excel file.")
        print(""" 
        Table definition:
            {}
        With subclasses:
            {}
            {}
            {}""".format(Session.definition, NeuronalRecording.definition, BehaviourRecording.definition,
                         BehaviourTrial.definition))

    @staticmethod
    def load_stimuli_from_tdms(tdmspath, software='behaviour'):
        """ Takes the path to a tdms file and attempts to load the stimuli metadata from it, returns a dictionary
         with the stim times """
        # TODO load metadata
        # Try to load a .tdms
        print('           ... loading stimuli time from .tdms: {}'.format(os.path.split(tdmspath)[-1]))
        try:
            tdms = TdmsFile(tdmspath)
        except:
            raise ValueError('Could not load .tdms file')

        if software == 'behaviour':
            stimuli = dict(audio=[], visual=[], digital=[])
            for group in tdms.groups():
                for obj in tdms.group_channels(group):
                    if 'stimulis' in str(obj).lower():
                        for idx in obj.as_dataframe().loc[0].index:
                            if '  ' in idx:
                                framen = int(idx.split('  ')[1].split('-')[0])
                            else:
                                framen = int(idx.split(' ')[2].split('-')[0])
                            if 'visual' in str(obj).lower():
                                visual_rec_stims.append(framen)
                            elif 'audio' in str(obj).lower():
                                audio_rec_stims.append(framen)
                            elif 'digital' in str(obj).lower():
                                digital_rec_stims.append(framen)
                            else:
                                print('                  ... couldnt load stim correctly')

            stimuli['visual'].append(visual_rec_stims)
            stimuli['audio'].append(audio_rec_stims)
            stimuli['digital'].append(digital_rec_stims)
        else:
            raise ValueError('Feature not implemented yet: load stim metdata from Mantis .tdms')
        return stimuli

    def create_trials_clips(self, BehavRec=None, folder=None, prestim=10, poststim=30):
        """
        This function creates small mp4 videos for each trial and saves them.
        It can work on a single BehaviouralRecording or on a whole folder

        :param BehavRec recording to work on, if None work on a whole folder
        :param folder  path to a folder containing videos to be processed, if None self.raw_video_folder
        """
        if BehavRec:
            raise ValueError('Feature not implemented yet: get trial clips for BehaviourRecording')
        else:
            if folder is None:
                video_fld = self.raw_video_folder
                metadata_fld = self.raw_video_folder
            else:
                raise ValueError('Feature not implemented yet: get trial clips for custom folder')

        editor = Editor()

        metadata_files = os.listdir(metadata_fld)

        for v in os.listdir(video_fld):
            if 'tdms' in v:
                raise ValueError('Feature not implemented yet: get trial clips from .tdms video')
            else:
                name = os.splitext(v)[0]
                tdms_file = [f for f in metadata_files if name in f]
                if len(tdms_file)>1: raise ValueError('Could not disambiguate video --> tdms relationship')
                else:
                    stimuli = self.load_stimuli_from_tdms(os.path.join(metadata_fld, tdms_file))

                    cap = cv2.VideoCapture(0)
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    window = (prestim*fps, poststim*fps)
                    clip_number_of_frames = window[1]-window[0]

                    for stim_type, stims in stimuli.items():
                        for stim in stims:
                            width, height = int(cap.get(3)), int(cap.get(4))
                            temp_data = np.zeros((width, height, clip_number_of_frames))

                            frame_n = stim-window[0]
                            cap.set(cv2.CV_CAP_PROP_POS_FRAMES, frame_n-1)
                            frame_counter = 0
                            while frame_n <= stim+window[1]:
                                frame, ret = cap.read()
                                if not ret:
                                    raise ValueError('something went wrong while trying to read the next frame')

                                temp_data[:,:, frame_counter] = frame
                                frame_counter += 1

                            video_path = os.path.join(self.trials_clips, name+'{}-{}'.format(stim_type, stim))

                            editor.opencv_write_clip(video_path, temp_data, w=width, h=height,
                                                     framerate=fps, start=0, stop=frame_counter)

    def sort_behaviour_files(self):
        for fld in os.listdir(self.raw_to_sort):
            for f in os.listdir(os.path.join(self.raw_to_sort, fld)):
                if '.tdms' in f and 'index' not in f:
                    copyfile(os.path.join(self.raw_to_sort, fld, f),
                             os.path.join(self.raw_metadata_folder, f))
                elif '.avi' in f:
                    os.rename(os.path.join(self.raw_to_sort, fld, f),
                              os.path.join(self.raw_to_sort, fld, fld+'.avi'))
                    copyfile(os.path.join(self.raw_to_sort, fld, fld+'.avi'), 
                             os.path.join(self.raw_metadata_folder, fld+'.avi'))
                else:
                    pass

