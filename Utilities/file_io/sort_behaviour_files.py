import sys
sys.path.append('./')  

import os
from shutil import copyfile

from Utilities.file_io.files_load_save import laod_yaml

def sort_behaviour_files(tosort_fld, video_fld, metadata_fld):
    yn = input('WARNING! this function only works with Behaviour software, NOT Mantis.\n Continue? y/n       ')
    if 'y' not in yn.lower(): return
    for fld in os.listdir(tosort_fld):
        for f in os.listdir(os.path.join(tosort_fld, fld)):
            print('sorting ', fld)
            if '.tdms' in f:
                if 'index' in f: continue
                dst = os.path.join(metadata_fld, f)
                if f in os.listdir(metadata_fld): 
                    print('Already moved')
                    continue
                else:
                    copyfile(os.path.join(tosort_fld, fld, f), dst)
            elif '.mp4' in f:
                dst = os.path.join(video_fld, fld+'.mp4')
                if fld+'.mp4' in os.listdir(video_fld):
                    print('Already moved')
                    continue
                else:
                    os.rename(os.path.join(tosort_fld, fld, f),
                                os.path.join(tosort_fld, fld, fld+'.mp4'))

                    copyfile(os.path.join(tosort_fld, fld, fld+'.mp4'), dst)
            else:
                raise ValueError('Could not proess file with format: ', os.path.split(f)[-1])
    print('... task completed')


def sort_mantis_files():
    # Get folders paths
    paths = load_yaml('paths.yml')
    raw = paths['raw_data_folder']
    metadata_fld = os.path.join(raw, paths['raw_metadata_folder'])
    video_fld = os.path.join(raw, paths['raw_video_folder'])
    tosort_fld = os.path.join(raw, paths['raw_to_sort'])

    # Loop over subfolders in tosort_fld
    for fld in os.listdir(tosort_fld):
        # Loop over individual files in subfolder
        for f in os.listdir(fld):
            pass
            # TODO


if __name__ == "__main__":
    from files_load_save import load_yaml
    paths = load_yaml('../../paths.yml')
    sort_behaviour_files(os.path.join(paths['raw_data_folder'], paths['raw_to_sort']),
                        os.path.join(paths['raw_data_folder'], paths['raw_video_folder']),
                        os.path.join(paths['raw_data_folder'], paths['raw_metadata_folder']))

