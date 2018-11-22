# -*- coding: utf-8 -*-

print('Importing deeplabcut takes a while...')
import os
import platform
import random
import sys
import platform

import deeplabcut
import yaml
print(' ... ready!')


class DLCManager:
    """
    Collection of useful functions for deeplabcut:

    ADD NEW VIDEOS TO EXISTING PROJECT
    deeplabcut.add_new_videos(`Full path of the project configuration file*',
    [`full path of video 4', `full path of video 5'],copy_videos=True/False)

    MANUALLY EXTRACT MORE FRAMES
    deeplabcut.extract_frames(‘config_path’,‘manual’)
    """

    """
        Typical pipeline for training a DLC network:

            - create project with videos
            - extract frames
            - label frames + check labels
            - creating training sets
            - train
            - evaluate -> make labelled videos and inspect by eye
            - enjoy

    """

    def __init__(self):
        # Get paths and settings
        # with open('paths.yml', 'r') as f:
        #    self.paths = yaml.load(f)

        with open('Tracking\dlcproject_config.yml', 'r') as f:
            self.settings = yaml.load(f)

        if 'windows' in platform.system().lower():
            self.dlc_paths = self.settings['paths-windows']
        else:
            self.dlc_paths = self.settings['paths-mac']

    ### MACROS

    def initialise_project(self):
        """  Create a projec with the training videos, extract the frames and start labeling gui """
        print('Creating project')
        self.create_project()
        print('Extracting frames')
        self.extract_frames()
        print('Labeling frames')
        self.label_frames()
    
    ### UTILS

    def sel_videos_in_folder(self, all=False, min_n=None):
        print('Getting videos')
        dr = self.dlc_paths['dr']
        if min_n is None:
            min_n = self.settings['min_num_vids']

        all_videos = [os.path.join(dr, f) for f in os.listdir(
            dr) if self.settings['video_format'] in f]

        if all or self.settings['number_of_training_videos'] >= len(all_videos):
            return all_videos
        else:
            selected_videos = random.sample(
                all_videos, self.settings['number_of_training_videos'])
            return selected_videos

    ### DLC functions

    def create_project(self):
        # TODO add check if file existsts already
        training_videos = self.sel_videos_in_folder()
        print('Creating project with {} videos'.format(len(training_videos)))

        deeplabcut.create_new_project(self.settings['experiment'], self.settings['experimenter'], 
                                      training_videos, working_directory=self.dlc_paths['project_path'], copy_videos=True)

    def add_videos_to_project(self, videos=None):     
        if videos is None:
            videos = self.sel_videos_in_folder()
        deeplabcut.add_new_videos(self.dlc_paths['cfg_path'], videos, copy_videos=True)

    def extract_frames(self):
        deeplabcut.extract_frames(self.dlc_paths['cfg_path'], 'automatic', self.settings['extract_frames_mode'], crop=False, checkcropping=False)

    def label_frames(self):
        print('Getting ready to label frames')
        deeplabcut.label_frames(self.dlc_paths['cfg_path']) #, Screens=1, winHack=1)

    def check_labels(self):
        deeplabcut.check_labels(self.dlc_paths['cfg_path'])

    def create_training_dataset(self):
        deeplabcut.create_training_dataset(self.dlc_paths['cfg_path'])

    def train_network(self):
        deeplabcut.train_network(self.dlc_paths['cfg_path'], shuffle=1, gputouse=0)

    def evaluate_network(self):
        deeplabcut.evaluate_network(self.dlc_paths['cfg_path'], plotting=True)

    def analyze_videos(self, videos=None):     
        if videos is None:
            videos = self.sel_videos_in_folder()
        else: 
            if not isinstance(videos, list):
                videos = [videos]
        deeplabcut.analyze_videos(self.dlc_paths['cfg_path'], videos, shuffle=1, save_as_csv=False)

    def create_labeled_videos(self, videos=None):
        if videos is None:
            videos = self.sel_videos_in_folder()
        else: 
            if not isinstance(videos, list):
                videos = [videos]
        deeplabcut.create_labeled_video(self.dlc_paths['cfg_path'],  videos)

    def extract_outliers(self, videos=None):
        if videos is None: videos = self.sel_videos_in_folder()
        deeplabcut.extract_outlier_frames(self.dlc_paths['cfg_path'], videos, automatic=True, 
                                          outlieralgorithm='jump', epsilon=20, p_bound=.01)

    def refine_labels(self):
        deeplabcut.refine_labels(self.dlc_paths['cfg_path'])

    def merge_datasets(self):
        deeplabcut.merge_datasets(self.dlc_paths['cfg_path'])

    def update_training_video_list(self):
            '''
            Updates the config.yaml file to include all videos in your labeled-data folder
            '''
            # load config file
            with open(self.dlc_paths['cfg_path']) as f:
                config_file = yaml.load(f)

            # create dict of labelled data folders
            updated_video_list = {}
            crop_dict_to_use = config_file['video_sets'][list(config_file['video_sets'].keys())[0]]
            training_images_folder = os.path.join(os.path.dirname(self.dlc_paths['cfg_path']), 'labeled-data')
            for i, folder in enumerate(os.listdir(training_images_folder)):
                if folder.find('labeled') < 0:
                    updated_video_list[os.path.join(self.dlc_paths['dr'], folder+'.'+self.settings['video_format'])] = crop_dict_to_use

            # replace video list in config file with new list
            config_file['video_sets'] = updated_video_list
            with open(self.dlc_paths['cfg_path'], "w") as f:
                yaml.dump(config_file, f)

        def delete_labeled_outlier_frames(self):
            '''
            Deletes the img.png files that are called 'labeled'
            '''
            # go through folders containing training images
            training_images_folder = os.path.join(os.path.dirname(self.dlc_paths['cfg_path']),'labeled-data')
            for i, folder in enumerate(os.listdir(training_images_folder)):
                if folder.find('labeled') < 0:
                    # for the unlabeled folders, delete the png images that are labeled
                    trial_images_folder = os.path.join(training_images_folder, folder)
                    for image in os.listdir(trial_images_folder):
                        if image.find('labeled.png')>=0:
                            os.remove(os.path.join(trial_images_folder, image))
                            
if __name__ == "__main__":
    manager = DLCManager()

    vids = manager.sel_videos_in_folder(all=False, min_n=2)

    # manager.analyze_videos(videos=vids)
    # manager.create_labeled_videos(videos=vids)
    # manager.extract_outliers(videos=vids)

    # manager.refine_labels()

    manager.merge_datasets()
    # manager.create_training_dataset()

    # manager.train_network()

"""

import tensorflow as tf
with tf.device('/gpu:0'):
    a = tf.constant([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], shape=[2, 3], name='a')
    b = tf.constant([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], shape=[3, 2], name='b')
    c = tf.matmul(a, b)

with tf.Session() as sess:
    print (sess.run(c))
"""
