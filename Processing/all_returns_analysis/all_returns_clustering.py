import sys
sys.path.append('./')
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.gridspec as gridspec
import matplotlib.pylab as pylab
params = {'legend.fontsize': 'x-large',
            'figure.figsize': (15, 15),
            'axes.labelsize': 'x-large',
            'axes.titlesize':'x-large',
            'xtick.labelsize':'x-large',
            'ytick.labelsize':'x-large',
            'font.size': 22}
pylab.rcParams.update(params)

import pandas as pd
from pandas.plotting import scatter_matrix
from collections import namedtuple
from itertools import combinations
from scipy.stats import gaussian_kde
import os
import seaborn as sn

from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics.pairwise import euclidean_distances
import scipy.cluster.hierarchy as shc
from sklearn.cluster import AgglomerativeClustering

from tsfresh import extract_relevant_features, extract_features
from tsfresh.utilities.dataframe_functions import impute

from Processing.tracking_stats.math_utils import line_smoother
from Utilities.file_io.files_load_save import load_yaml
from Processing.rois_toolbox.rois_stats import get_roi_at_each_frame

from Processing.all_returns_analysis.all_returns_database import *


class cluster_returns:
    def __init__(self):
        self.group_by = 'is trial'

        # Get and cleanup data
        analysis = analyse_all_trips()
        self.data = analysis.returns_summary
        self.anonymous_data = self.data.copy()
        self.anonymous_data = self.anonymous_data.drop(
            ['is trial', 'is fast', 'shelter_stay', 'threat_stay'], 1)
        
        # Features engineering and data minining
        self.expand_data()
        self.inspect_data()
        
        # Do PCA and K-means
        self.pca_components = self.do_pca()
        self.clustered = self.kmeans()

        # Plot stuff
        self.check_clustering()
        self.plot_points_density()

        plt.show()

    def expand_data(self):
        # to_square = ['x_displacement', 'length', 'duration']
        # for ts in to_square:
        #     squared = self.anonymous_data[ts].values
        #     self.anonymous_data['squared_'+ts] = pd.Series(np.square(squared))

        self.anonymous_data['dur_by_len'] = pd.Series(np.divide(
            self.anonymous_data['duration'].values, self.anonymous_data['length'].values))

    def inspect_data(self):
        self.anonymous_data.describe()
        self.anonymous_data.hist()
        self.corrr_mtx = self.anonymous_data.corr()

        for k in self.corrr_mtx.keys():
            print('\n Correlation mtx for {}'.format(k))
            print(self.corrr_mtx[k])

        n = len(self.anonymous_data.columns)
        scatter_matrix(self.anonymous_data, alpha=0.2,
                        figsize=(6, 6), diagonal='kde')

        trials = self.anonymous_data.loc[self.data[self.group_by] == 1]
        not_trials = self.anonymous_data.loc[self.data[self.group_by] == 0]

        f, axarr = plt.subplots(n, 4, facecolor=[.8, .8, .8])
        axarr = axarr.flatten()
        combs = combinations(list(self.anonymous_data.columns), 2)
        counter = 0
        for i, (c1, c2) in enumerate(combs):
            if 'trial' in c1 or 'trial' in c2:
                continue
            ax = axarr[counter]
            counter += 1
            ax.set(facecolor=[.2, .2, .2],
                title='{}-{}'.format(c1, c2), xlabel=c1, ylabel=c2)
            ax.scatter(trials[c1].values, trials[c2].values,
                    c=[.8, .2, .2], alpha=.2)
            ax.scatter(not_trials[c1].values,
                    not_trials[c2].values, c=[.2, .2, .8], alpha=.2)


    def plot_points_density(self):
        x = self.pca_components['principal component 1'].values
        y = self.pca_components['principal component 2'].values

        # Calculate the point density
        xy = np.vstack([x, y])
        z = gaussian_kde(xy)(xy)

        # Sort the points by density, so that the densest points are plotted last
        idx = z.argsort()
        x, y, z = x[idx], y[idx], z[idx]

        fig, ax = plt.subplots(figsize=(5, 5), facecolor=[.2, .2, .2])
        ax.scatter(x, y, c=z, s=50, edgecolor='')
        ax.set(facecolor=[.8, .8, .8])

    def kmeans(self):
        clustered_data = {}

        # create kmeans object
        f, axarr = plt.subplots(6, 1, facecolor=[.2, .2, .2])
        axarr = axarr.flatten()
        costs = []
        for c in range(2, 6):
            n_clusters = c
            ax = axarr[c-2]

            kmeans = KMeans(n_clusters=n_clusters)

            # fit kmeans object to data
            data = self.pca_components.drop([self.group_by], 1)
            kmeans.fit(data)

            # save new clusters for chart
            y_km = kmeans.fit_predict(self.anonymous_data)
            clustered_data[str(c)] = y_km

            # check results
            for i in range(n_clusters):
                t = data.loc[y_km == i]
                ax.scatter(t['principal component 1'],
                        t['principal component 2'],
                        s=30, alpha=.2)
            ax.set(facecolor=[.2, .2, .2], title='{} Clusters'.format(c))

            interia = kmeans.inertia_
            print("k:", c, " cost:", round(interia))
            costs.append(round(interia))
        return clustered_data

    def check_clustering(self):
        f, axarr = plt.subplots(4, 1, facecolor=[.2, .2, .2])
        trials = self.data.loc[self.data[self.group_by] == 1]

        for ax in axarr:
            ax.set(facecolor=[.2, .2, .2], title='velocity by cluster')
            _, bins, _ = ax.hist(
                trials['velocity'].values, bins=100, color=[.9, .9, .9], label='trials')

        for c, (k, v) in enumerate(self.clustered.items()):
            ax = axarr[c]
            for i in range(int(k)):
                t = self.data.loc[v == i]
                ax.hist(t['velocity'].values, bins=bins,
                        label=str(i), alpha=.3)
        [ax.legend() for ax in axarr]

    def plot_pca(self, df):
        f, ax = plt.subplots(facecolor=[.2, .2, .2])
        d = dict(not_trials=(0, [.4, .4, .8], .4),
                trials=(1, [.8, .4, .4], .4),)

        ax.set(facecolor=[.2, .2, .2])
        for n, (i, c, a) in d.items():
            indicesToKeep = df[self.group_by] == i
            ax.scatter(df.loc[indicesToKeep, 'principal component 1'],
                    df.loc[indicesToKeep, 'principal component 2'], c=c, alpha=a, s=30, label=n)

        # Plot a line
        # ax.plot([-2.5, 1], [2, -2], '--', color=[.4, .8, .4], linewidth=3)

        ax.legend()

    def do_pca(self):
        x = self.anonymous_data.values
        scaled = StandardScaler().fit_transform(x)

        pca = PCA(n_components=2)
        principalComponents = pca.fit_transform(scaled)
        principalDf = pd.DataFrame(data=principalComponents, columns=[
                                'principal component 1', 'principal component 2'])
        finalDf = pd.concat([principalDf, self.data[self.group_by]], axis=1)

        print(pd.DataFrame(pca.components_,
                        columns=self.anonymous_data.columns, index=['PC-1', 'PC-2']))

        # Logistic Regression
        # _training_set, _test_set = train_test_split(finalDf.values, test_size=0.2, random_state=42)
        # training_set, training_labels = _training_set[:, :2], _training_set[:, -1]
        # test_set, test_labels = _test_set[:, :2], _test_set[:, :-1]
        # logisticRegr = LogisticRegression(solver = 'lbfgs')
        # logisticRegr.fit(training_set, training_labels)

        # predictions = logisticRegr.predict(test_set)
        # predictions = predictions.astype(int)
        # predictionsDf = pd.DataFrame(data=predictions, columns=['is trial'])
        # predictedDf = pd.concat([principalDf, predictionsDf['is trial']], axis = 1)

        # # print(logisticRegr.score(test_set.round(), test_labels.round()))

        # self.plot_pca(predictedDf)
        self.plot_pca(finalDf)

        return finalDf


class timeseries_returns:
    def __init__(self, load=False, trace=1):
        self.select_seconds = 20
        self.fps = 30
        self.n_clusters = 3
        self.sel_trace = trace # 1 for Y and 2 for V

        analysis = analyse_all_trips()

        # paths_names = ['Left_Far', 'Left_Medium', 'Centre', 'Right_Medium', 'Right_Far']
        paths_names = ['Right_Medium' ]    
        for self.path_n, self.path_name in enumerate(paths_names):
            if load:
                distance_mtx = np.load('Processing\\all_returns_analysis\\distance_mtx.npy')
            else:
                # Get prepped data
                self.data = analysis.returns_summary

                # Select returns - get tracking data
                self.data = self.prep_data()
                y, y_dict, y_list = self.get_y(self.data)
                
                # Get euclidean distance
                distance_mtx = self.distance(y)
            print('Got distance matrix')

            # Cluster 
            cluster_obj, self.data['cluster labels'] = self.cluster(distance_mtx)
            
            # Plot clusters

            # self.plot_all_heatmap()
            # self.plot_dendogram(distance_mtx)
            # self.plot_clusters_heatmaps()

            # Multivariate Time Series Analysis
            self.mvt_analysis()

    @staticmethod
    def convert_y_to_df(y):
        index = ['c{}'.format(i) for i in range(y.shape[1])]
        data = {idx:y[:,i] for i,idx in enumerate(index)}
        return pd.DataFrame.from_dict(data) 

    @staticmethod
    def features_extractor(y)

    def mvt_analysis(self):
        print('extracting features')
        v, _, vl = self.get_y(self.data, sel=2)
        y, _, yl = self.get_y(self.data, sel=1)

        v = self.convert_y_to_df(v)
        fake = np.zeros((len(vl)))
        v['id'] = np.zeros(v.shape[0])

        a = 1

    def prep_data(self):
        """prep_data [Select only returns along the R medium arm]
        """
        lims = dict(Left_Far=(-10000, -151),
                    Left_Medium=(-150, -100),
                    Centre=(-99, 99),
                    Right_Medium= (100, 150),
                    Right_Far= (151, 10000))
        lm = lims[self.path_name]
        # 100, 150
        new_data = self.data.loc[(self.data['x_displacement'] >= lm[0]) &
                                (self.data['x_displacement'] <= lm[1])]
        return new_data
    
    def get_y(self, arr, sel=None):
        length = self.select_seconds*self.fps
        y = np.zeros((length, arr.shape[0]))
        y_dict, y_list = {}, []
        
        
        if sel is None: sel = self.sel_trace
        for i, (idx, row) in enumerate(arr.iterrows()):
            t0, t_shelt = row['times']
            t1 = t0 + self.select_seconds*self.fps
            
            yy = np.array(np.round(row['tracking_data'][t0:t1, sel], 2), dtype=np.double)
            if self.sel_trace == 2:
                yy[yy>20] = np.mean(yy)
                # yy = self.array_scaler(yy)

            y[:yy.shape[0], i] = yy
            y_dict[str(i)] = np.array(yy)
            y_list.append(np.array(yy))
        return y, y_dict, y_list

    def plot_returns(self, var, ttl=''):
        titles = ['x', 'y', 'xy', 'vel']
        ylims = [[400, 700], [300, 800], [350, 800], [0, 25]]
        length = self.select_seconds*self.fps
        
        f, axarr = plt.subplots(2, 2)
        axarr = axarr.flatten()
        
        for idx, row in var.iterrows():
            t0, t_shelt = row['times']
            x_t_shelt = t_shelt-t0
            t1 = t0 + length

            # Plot traces
            axarr[0].plot(row['tracking_data'][t0:t1, 0], 'k', alpha=.2)
            axarr[1].plot(row['tracking_data'][t0:t1, 1], 'k', alpha=.2)
            axarr[2].plot(row['tracking_data'][t0:t1, 0], row['tracking_data'][t0:t1, 1], 'k', alpha=.2)
            axarr[3].plot(line_smoother(row['tracking_data'][t0:t1, 2]), 'k', alpha=.15)
            
            # Mark moment shelter is reached
            if x_t_shelt <= length:
                axarr[0].plot(x_t_shelt, row['tracking_data']
                                [t_shelt, 0], 'o', color='r', alpha=.3)
                axarr[1].plot(x_t_shelt, row['tracking_data']
                                [t_shelt, 1], 'o', color='r', alpha=.3)
                # axarr[3].plot(x_t_shelt, row['tracking_data'][t_shelt, 2], 'o', color='r', alpha=.3)
            axarr[2].plot(row['tracking_data'][t_shelt, 0],
                            row['tracking_data'][t_shelt, 1], 'o', color='r', alpha=.3)

        [ax.set(title=titles[i]+'  '+ttl, ylim=ylims[i]) for i, ax in enumerate(axarr)]

    @staticmethod
    def array_scaler(x):
        """Scales array to 0-1
        
        Dependencies:
            import numpy as np
        Args:
            x: mutable iterable array of float
        returns:
            scaled x
        """
        arr_min = np.min(x)
        x = np.array(x) - float(arr_min)
        arr_max = np.max(x)
        x = np.divide(x, float(arr_max))
        return x

    def distance(self, y):
        return euclidean_distances(y.T, y.T)

    def cluster(self, dist, plot=False):
        cluster = AgglomerativeClustering(n_clusters=self.n_clusters, affinity='euclidean', linkage='ward')  
        labels = cluster.fit_predict(dist)  
        
        if plot:
            f, axarr = plt.subplots(2, 1)
            axarr = axarr.flatten()
            for i in range(y.shape[1]):
                clst = labels[i]
                axarr[clst].plot(y[:, i], 'k', alpha=.5)  
        return cluster, labels

    def plot_clusters_heatmaps(self):
        clusters_ids = set(self.data['cluster labels'])
        
        f, axarr = plt.subplots(2, len(clusters_ids))

        for _id in clusters_ids:
            selected = self.data.loc[self.data['cluster labels']==_id]
            y, y_dict, y_list = self.get_y(selected)

            axarr[0, _id].plot(y, color='k', alpha=.1)
            axarr[0, _id].plot(np.mean(y, 1), color='r', linewidth=3)
            sn.heatmap(y.T, ax=axarr[1, _id], )
            axarr[1, _id].set(title='{} - Cluster # {}'.format(self.path_name, _id))

    def plot_all_heatmap(self):
        cmap = 'inferno'
        y,_,_ = self.get_y(self.data)
        y = np.fliplr(np.sort(y))

        if self.sel_trace == 1:
            vmax, vmin = 750, 350
        else:
            vmax, vmin = 15, -2

        f, ax = plt.subplots()
        sn.heatmap(y.T, ax=ax, cmap=cmap, xticklabels=False, vmax=vmax, vmin=vmin)
        ttls = ['', 'Y trace', 'V trace']
        ax.set(title=self.path_name+' '+ttls[self.sel_trace]+' '+cmap)

    def plot_dendogram(self, dist): 
        " plot the dendogram and the trace heatmaps divided by stimulus/spontaneous and cluster ID"
        print('Plotting...')

        # Create figure and axes
        plt.figure()
        clusters_ids = set(self.data['cluster labels'])    
        gs = gridspec.GridSpec(3, len(clusters_ids))
        dendo_ax = plt.subplot(gs[0, :])
        stim_axes = [plt.subplot(gs[1, i]) for i in range(len(clusters_ids))]
        spont_axes = [plt.subplot(gs[2, i]) for i in range(len(clusters_ids))]

        # Define some params for plotting
        if self.sel_trace == 1:
            center = 560
            cmap = 'bwr'
            vmax, vmin = 750, 350
        else:
            center = 7
            cmap = 'bwr'
            vmax, vmin = 15, 2.5

        # Plot dendogram
        ttls = ['', 'Y trace', 'V trace']
        dend = shc.dendrogram(shc.linkage(dist, method='ward'), ax=dendo_ax, no_labels=True, truncate_mode = 'level', p=6) # , orientation='left')
        dendo_ax.set(title=self.path_name+' Clustered by : '+ttls[self.sel_trace])
        # Plot clusters heatmaps
        for i, clust_id in enumerate(list(clusters_ids)[::-1]):
            # Get data
            stim_evoked =  self.data.loc[(self.data['cluster labels']==clust_id)&(self.data['is trial']==1)]
            spontaneous =  self.data.loc[(self.data['cluster labels']==clust_id)&(self.data['is trial']==0)]
        
            stim_y, _, _ = self.get_y(stim_evoked)
            spont_y, _, _ = self.get_y(spontaneous)
            
            stim_y = np.fliplr(np.sort(stim_y))
            spont_y = np.fliplr(np.sort(spont_y))
            # y = y[:, :150]
        
            # Plot heatmaps
            if i == len(clusters_ids):
                show_cbar = True
            else:
                show_cbar = False
            sn.heatmap(stim_y.T, ax=stim_axes[i], center=center, cmap=cmap, 
                        xticklabels=False, vmax=vmax, vmin=vmin, cbar=show_cbar)
            sn.heatmap(spont_y.T, ax=spont_axes[i], center=center, cmap=cmap, 
                        xticklabels=False, vmax=vmax, vmin=vmin, cbar=show_cbar)

            # Set titles and stuff
            stim_axes[i].set(title="Stim. evoked - cluster {}".format(clust_id))
            spont_axes[i].set(title="Spontaneous - cluster {}".format(clust_id))



if __name__ == '__main__':
    #cluster_returns()

    timeseries_returns(load=False, trace=1)
    timeseries_returns(load=False, trace=2)
    plt.show()
