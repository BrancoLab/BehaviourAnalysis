# %%
import sys
sys.path.append('./')   # <- necessary to import packages from other directories within the project
from Utilities.imports import *

from Processing.psychometric_analysis import PsychometricAnalyser
pa = PsychometricAnalyser()

from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 unused import
from matplotlib import cm
from matplotlib.ticker import LinearLocator, FormatStrFormatter
from matplotlib.gridspec import GridSpec
from mpl_toolkits.axes_grid1 import make_axes_locatable
from scipy.optimize import minimize

# %matplotlib inline

# %%
# set seaborn
import seaborn as sns
sns.set()
sns.set_style("white", {
            "axes.grid":"False",
            "ytick.right":"False",
            "ytick.left":"True",
            "xtick.bottom":"True",
            "text.color": "0"
})
mpl.rc('text', usetex=False)

params = {
    'text.latex.preamble': ['\\usepackage{gensymb}'],
    'image.origin': 'lower',
    'image.interpolation': 'nearest',
    'image.cmap': 'gray',
    'axes.grid': False,
    'savefig.dpi': 150,  # to adjust notebook inline plot size
    'axes.labelsize': 8, # fontsize for x and y labels (was 10)
    'axes.titlesize': 8,
    'font.size': 8, # was 10
    'legend.fontsize': 6, # was 10
    'xtick.labelsize': 8,
    'ytick.labelsize': 8,
    'text.usetex': False,        # ! <----- use TEX
    'figure.figsize': [3.39, 2.10],
}
mpl.rcParams.update(params)
sns.set_context("talk", font_scale=1)  # was 3 


# %%
class PsiCalculator:
    use_diff_rho = False # ! define rho as l-r instead of l/r
    colors = [lightblue, green, purple, magenta]
    good_fit_params = ([0.6, 0.8, 0],[0.9, 10, 2])

    lw = 2   # 6
    dotsize = 800

    def __init__(self):
        self.R = np.arange(0, 1001, 1)
        self.L = np.arange(0, 1001, 1)
        self.Psi = np.zeros((len(self.R), len(self.R)))
        self.PsidL, self.PsidR = np.zeros_like(self.Psi), np.zeros_like(self.Psi)

        # ? Psi params
        self.o = 0.6
        self.r0 = 1
        self.s = 10

        self.update_params()

        self.npoints = len(self.R)
        self.rmax = np.int(np.max(self.R))
        self.points_conversion_factor = self.rmax/self.npoints
        self.colorshelper = MplColorHelper("Greens", 0, self.rmax+self.rmax/4, inverse=True)

        # Experimental data
        self.prs = [0.78, 0.72, 0.70, 0.47]
        # yerr: [2* math.sqrt(s) for s in list(sigmasquared.values())]
        self.yerrs = [0.048042182449778245, 0.0689335245891631, 0.06165147992851076, 0.07914616013894715]
        self.pathlengths = pa.paths_lengths.distance.values
        self.R0 = np.min(self.pathlengths)
        self.rhos = [round(y/self.R0, 2) for y in self.pathlengths]
        self._pathlengths = pa.paths_lengths.distance.values  # use a copy for scaling
        self._rhos = [round(y/self.R0, 2) for y in self.pathlengths]


    # ! Utilities
    def update_params(self):
        self.default_params = {
            "o":self.o, 
            "r0":self.r0,
            "s":self.s
        }

    def scale_pathlengths(self, r0):
        # Scale path length so that the right arm has length r0
        alpha = self._pathlengths[-1] / r0
        self.pathlengths = self._pathlengths / alpha


        self.rhos = [round(y/r0, 2) for y in self.pathlengths]
    
    def get_arr_idx(self, x,):
        # get the index in the value closest to x
        return np.int(x*self.npoints / self.rmax)

    @staticmethod
    def clean_axes(f=None):
        sns.despine(fig=f, offset=10, trim=False, left=False, right=True)

    # ! Calculations on Psi
    def calc_Psi(self, l, r, o=1, r0=2, s=10):
        """
        2D logistic
        l, r = values
        o = omega, scales the function in the Z direction
        r0 = value of l/r at which Psi=0.5
        s = slope
        """ 
        b = (1 - o)/2  # -> this ensures that the logistic is always centered on z=.5
        if not self.use_diff_rho:
            rho = l/r
        else:
            rho = l - r

        delta_rho = rho - r0
        z = o / (1 + np.exp(-s*(delta_rho)))+b
        return z

    def calc_Psi_slice(self, l, o=1, s=10, r0=1, ):
        """
            Calcs the value of Psi along the vertical slice corresponiding to r0
        """ 
        return self.calc_Psi(l, self.R0, o=o, r0=r0, s=s)

    @staticmethod
    def dPsy_dL(l, r, o=1, r0=1, s=10):
        # returns the partial derivative of Psi over L at l,r
        e = np.exp(-(s*(l-r)/r))
        return (o*s*e)/((r*(1 + e)**2))

    @staticmethod
    def dPsy_dR(l, r, o=1, r0=1, s=10):
        # returns the partial derivative of Psi over R at l,r
        e = np.exp(-(s*(l-r)/r))

        return -((o*l*s*e)/((r**2)*(1+e)**2))

    def getPsi(self):
        for i, r in enumerate(self.R):
            for ii, l in enumerate(self.L):
                self.Psi[ii, i] = self.calc_Psi(l, r, **self.default_params)
                self.PsidL[ii, i] = self.dPsy_dL(l, r, **self.default_params)
                self.PsidR[ii, i] = self.dPsy_dR(l, r, **self.default_params)


    # ! Plotting
    def plot_Psi(self, calc=False, ax=None, f=None, cbar=True):
        if calc: self.getPsi()

        if ax is None: f, ax = create_figure(subplots=False)

        surf = ax.imshow(self.Psi, extent=[0, self.rmax, 0, self.rmax], cmap=cm.coolwarm, origin="lower", aspect="equal", vmin=0, vmax=1)
        divider = make_axes_locatable(ax)
        cax1 = divider.append_axes("right", size="5%", pad=0.15)

        if cbar: 
            f.colorbar(surf, cax=cax1)

        ax.set(title="$\\Psi(\\rho)$", xlabel="$R$", ylabel="$L$", xticks=[0, self.rmax], yticks=[0, self.rmax])
        
        self.clean_axes()
        return ax

    def plot_Psy_derivs(self, calc=False):
        if calc: self.getPsi()

        f, axarr = create_figure(subplots=True, ncols=3, nrows=2)
        surf = axarr[0].imshow(self.Psi, extent=[0, self.rmax, 0, self.rmax], cmap=cm.coolwarm, origin="lower", aspect="equal", vmin=0, vmax=1)
        surf = axarr[1].imshow(self.PsidL, extent=[0, self.rmax, 0, self.rmax], cmap=cm.coolwarm, origin="lower", aspect="equal", vmin=0, vmax=.005)
        surf = axarr[2].imshow(self.PsidR, extent=[0, self.rmax, 0, self.rmax], cmap=cm.coolwarm, origin="lower", aspect="equal", vmax=0, vmin=-.005)

        eval_values = np.arange(100, self.rmax, 100)
        lslopes, rslopes = [], []
        for r0 in eval_values:
            r0idx = self.get_arr_idx(r0)
            color = self.colorshelper.get_rgb(r0)
            axarr[0].axvline(r0, color=color, lw=self.lw*0.75, ls="--")
            axarr[1].axvline(r0, color=color, lw=self.lw*0.75, ls="--")
            axarr[2].axhline(r0, color=color, lw=self.lw*0.75, ls="--")

            axarr[3].plot(self.Psi[:, r0idx], color=color, lw=self.lw)
            axarr[4].plot(self.PsidL[:, r0idx], color=color, lw=self.lw)
            axarr[5].plot(self.PsidR[r0idx, :], color=color, lw=self.lw)

            lslopes.append(self.PsidL[:, r0idx])
            rslopes.append(self.PsidR[r0idx, :])

        xticklabels = ["${}$".format(x) for x in np.arange(0, self.rmax+1, 100)]
        axarr[3].set(xlabel="$L$", ylabel="$\Psi$", yticks=[0, round(np.nanmin(self.Psi),2), round(np.nanmax(self.Psi),2), 1], 
                        xticks=np.arange(0, self.npoints, np.int(250*self.points_conversion_factor)), xticklabels=["${}$".format(x) for x in np.arange(0, self.rmax+1, 100)])
        axarr[4].set(xlabel="$R$", yticks=[0, round(np.nanmax(lslopes), 3)], 
                        xticks=np.arange(0, self.npoints, np.int(250*self.points_conversion_factor)), xticklabels=["${}$".format(x) for x in np.arange(0, self.rmax+1, 250)])
        axarr[5].set(xlabel="$L$", yticks=[0, round(np.nanmin(rslopes), 3)], 
                        xticks=np.arange(0, self.npoints, np.int(250*self.points_conversion_factor)), xticklabels=["${}$".format(x) for x in np.arange(0, self.rmax+1, 250)])

        titles = ["$\Psi$", "$\\frac{\\partial \\Psi}{\\partial L}$", "$\\frac{\\partial \\Psi}{\\partial R}$"]
        for ax, t in zip(axarr, titles):
            ax.set(title=t, xticks=[], yticks=[], xlabel="$R$", ylabel="$L$")

        self.clean_axes(f=f)

    def plot_Psi_schematic(self):
        # ? Make figure for upgrade
        f, ax = create_figure(subplots=False)

        z = np.zeros_like(self.Psi)
        for i, xx in enumerate(self.R):
                for ii, yy in enumerate(self.L):
                        if xx == yy:
                                p = .5
                        elif xx > yy:
                                p = 1
                        else:
                                p = 0
                        z[i, ii] = p

        surf = ax.imshow(z, extent=[0, self.rmax, 0, self.rmax], cmap=cm.coolwarm, origin="lower", aspect="equal", vmin=0, vmax=1)
        divider = make_axes_locatable(ax)
        cax1 = divider.append_axes("right", size="5%", pad=0.15)
        f.colorbar(surf, cax=cax1)

        ax.set(title="$\Psi(\\rho)$", xlabel="$R$", ylabel="$L$", xticks=[0, self.rmax], yticks=[0, self.rmax])
        self.clean_axes(f=f)

    def plot_mazes_IC(self, ax=None, f=None, cbar=True):
        if ax is None: 
            ax = self.plot_Psi()
        else:
            self.plot_Psi(ax=ax, f=f, cbar=cbar)
        vline_to_point(ax, self.R0, np.max(self.pathlengths), color=black, lw=self.lw, ls="--")

        for L,c in zip(self.pathlengths, self.colors):
            ax.plot([0, self.rmax], [0, self.rmax*(L/self.R0)], color=c, lw=self.lw)
            ax.scatter(self.R0, L, color=c, s=self.dotsize, edgecolors=black, zorder=20)
        ax.set(title="$\Psi(\\rho)$", xlabel="$R$", ylabel="$L$", xticks=[0,  self.R0, self.rmax], yticks=[0, self.rmax], xlim=[0, self.rmax], ylim=[0, self.rmax])
        
        self.clean_axes(f=f)
        return ax

    def plot_mazes(self, ax=None, f=None, cbar=True, calc=False):
        if ax is None: 
            ax = self.plot_Psi()
        else:
            self.plot_Psi(ax=ax, f=f, cbar=cbar, calc=calc)

        vline_to_point(ax, self.R0, np.max(self.pathlengths), color=black, lw=self.lw, ls="--")

        yticks = [0]
        yticks.extend(list(self.pathlengths))
        yticks.extend([self.rmax])

        for L,c in zip(self.pathlengths, self.colors):
            hline_to_point(ax, self.R0, L, color=c, lw=self.lw, ls="--")
            ax.scatter(self.R0, L, color=c, s=self.dotsize, edgecolors=black, zorder=20)
        ax.set(title="$\Psi(\\rho)$", xlabel="$R$", ylabel="$L$", xticks=[0,  self.R0, self.rmax], 
        yticks=yticks, xlim=[0, self.rmax], ylim=[0, self.rmax])

        self.clean_axes(f=f)
        return ax

    def fit_plot(self, fit_bounds=None):
        if fit_bounds is None:
            fit_bounds = self.good_fit_params

        # Plot the fit of the Psi function to the data
        f, axarr = create_figure(subplots=True, ncols=2)
        
        xlbls, ylbls = [0], [0]
        for L, c, pr, yerr in zip(self.pathlengths, self.colors, self.prs, self.yerrs):
            axarr[0].scatter(L, pr, color=c, s=self.dotsize, edgecolors=black, zorder=20)
            hline_to_point(axarr[0], L, pr, color=black, lw=self.lw, ls="--")
            vline_to_point(axarr[0], L, pr, color=c, lw=self.lw, ls="--")
            xlbls.append(np.int(L))
            ylbls.append(pr)

        xlbls.append(1000)
        ylbls.append(1)

        params = plot_fitted_curve(self.calc_Psi_slice, self.pathlengths, self.prs, axarr[0], 
            xrange=[0, self.rmax],
            fit_kwargs={"sigma":self.yerrs, "method":"dogbox", "bounds":fit_bounds},
            scatter_kwargs={"alpha":0, "s":self.dotsize}, 
            line_kwargs={"color":black, "alpha":1, "lw":2,})

        axarr[0].set(xlim=[0, self.rmax], ylim=[0, 1], xlabel="$L$", ylabel="$\Psi$",
                        xticks=xlbls, xticklabels=["${}$".format(x) for x in xlbls], yticks=ylbls, yticklabels=["${}$".format(y) for y in ylbls])


        print(""" 
            Fitted sigmoid:
                omega: {}
                slope: {}
                x0:    {}
        
        """.format(round(params[0], 2), round(params[1], 2), round(params[2], 2)))

        self.o = params[0]
        self.r0 = params[2]
        self.s = params[1]
        self.update_params()

        # Plot image and  set axes dimensions
        ax = self.plot_mazes(ax=axarr[1], f=f, cbar=True, calc=True)

        gs = GridSpec(1, 3, width_ratios=[1, 1, .25], height_ratios=[1])
        for i in range(len(axarr)):
            axarr[i].set_position(gs[i].get_position(f))

        self.clean_axes(f=f)

    def slope_analysis(self):
        # Look at the slope of the partial over L for different values of R
        slopes, colors, x_correct = [], [], []
        x = np.arange(0, self.npoints, 10)

        for r in x:
            slope = self.PsidL[r, r]
            if np.isnan(slope) or np.isinf(slope): continue
            x_correct.append(r)
            slopes.append(slope)
            colors.append(self.colorshelper.get_rgb(r*self.points_conversion_factor))

        f, ax = create_figure(subplots=False)

        # Plot data and fit an exponential
        params = plot_fitted_curve(exponential, x_correct, slopes, ax,
            xrange=[0, np.max(x_correct)],
            fit_kwargs={"method":"dogbox", "max_nfev":1000, "bounds":([0.5, -3, 0, 0], [1, 0, 1, 0.6])},
            scatter_kwargs=dict(c=colors, edgecolors=black, s=self.dotsize),
            line_kwargs=dict(color=red, lw=self.lw, ls="--")
        
        )
        ax.set(title="$\\left.\\frac{\\partial \\Psi}{\\partial L}\\right|_{L=R}$", xlabel="$L$", ylabel="$Slope$", xticks=np.arange(0, self.npoints, np.int(250*self.points_conversion_factor)), xticklabels=np.arange(0, self.rmax+1, 250))

        self.slope_data = np.zeros((len(slopes), 2))
        self.slope_data[:, 0], self.slope_data[:, 1] = x_correct, slopes
        
        self.clean_axes(f=f)

    def plot_slices(self):
        f, axarr = create_figure(subplots=True, ncols=3, nrows=1)

        surf = axarr[0].imshow(self.Psi, extent=[0, self.rmax, 0, self.rmax], cmap=cm.coolwarm, origin="lower", aspect="equal", vmin=0, vmax=1)

        eval_values = np.arange(100, self.rmax, 100)
        lslopes, rslopes = [], []
        for r0 in eval_values:
            r0idx = self.get_arr_idx(r0)
            color = self.colorshelper.get_rgb(r0)
            axarr[0].axvline(r0, color=color, lw=self.lw*.75, ls="--")
            axarr[0].axhline(r0, color=color, lw=self.lw*.75, ls="--")

            axarr[1].plot(self.Psi[:, r0idx], color=color, lw=self.lw)
            axarr[2].plot(self.Psi[r0idx, :], color=color, lw=self.lw)

        axarr[0].set(title="$\Psi$", xticks=[], yticks=[], xlabel="$R$", ylabel="$L$")
        axarr[1].set(title="$R\\ constant$",  xlabel="$L$", ylabel="$\Psi$", yticks=[0, round(np.nanmin(self.Psi),2), round(np.nanmax(self.Psi),2), 1], xticks=np.arange(0, self.npoints, np.int(250*self.points_conversion_factor)), xticklabels=np.arange(0, self.rmax+1, 100))
        axarr[2].set(title="$L\\ constant$",xlabel="$R$", ylabel="$\Psi$", yticks=[0, round(np.nanmin(self.Psi),2), round(np.nanmax(self.Psi),2), 1], xticks=np.arange(0, self.npoints, np.int(250*self.points_conversion_factor)), xticklabels=np.arange(0, self.rmax+1, 100))

        self.clean_axes(f=f)

    def plot_ICs(self):
        f, ax = create_figure(subplots=False)

        levels = np.arange(-.1, 1.11, .1)
        h = MplColorHelper("gray", -0., 2.11, inverse=False)
        colors = [h.get_rgb(l) for l in levels]

        contours = ax.contour(self.R, self.L, self.Psi, levels=levels, colors=colors)
        ax.clabel(contours, inline=1, fontsize=10, colors=colors)
        ax.imshow(self.Psi, extent=[0, self.rmax, 0, self.rmax], cmap=cm.coolwarm, origin="lower", aspect="equal", vmin=0, vmax=1)


    def text(self):
        f, ax = create_figure(subplots=False)

        ax.set(title="$abcdefghilmno-ABCDEFGHIJKLMNOPQRST()$")


#%%
calc = PsiCalculator()
calc.getPsi()

# calc.plot_slices()
# calc.plot_Psy_derivs()
# calc.slope_analysis()
# calc.plot_mazes_IC()
# calc.plot_Psi()
# calc.text()
# calc.plot_mazes()
calc.fit_plot()


# plt.show()

#%%
class Algomodel:
    colors = [lightblue, green, purple, magenta]
    lw = 2
    dotsize = 300

    sigma_scaling = 4.35 # Determined by fittnig

    def __init__(self):
        # Experimental data
        self.prs = dict(
                        maze1 = 0.78, 
                        maze2 = 0.72, 
                        maze3 = 0.70, 
                        maze4 = 0.47)

        self.yerrs = [0.048042182449778245, 0.0689335245891631, 0.06165147992851076, 0.07914616013894715]
        self.pathlengths = pa.paths_lengths.distance.values
        self.R0 = np.min(self.pathlengths)
        self.rhos = [round(y/self.R0, 2) for y in self.pathlengths]
        self._pathlengths = pa.paths_lengths.distance.values  # use a copy for scaling
        self._rhos = [round(y/self.R0, 2) for y in self.pathlengths]

        maze = namedtuple("arms", "l r")
        self.mazes = dict(
            maze1 = maze(self.pathlengths[0], self.pathlengths[-1]),
            maze2 = maze(self.pathlengths[1], self.pathlengths[-1]),
            maze3 = maze(self.pathlengths[2], self.pathlengths[-1]),
            maze4 = maze(self.pathlengths[3], self.pathlengths[-1]),
        )
        self.model_prs = {k:0 for k,v in self.mazes.items()}



        self.R = np.arange(0, 1001, 1)
        self.L = np.arange(0, 1001, 1)
        self.us_prs = np.zeros((len(self.R), len(self.R)))  # p(R) at all locations in utility space
        self.npoints = len(self.R)
        self.rmax = np.int(np.max(self.R))
        self.points_conversion_factor = self.rmax/self.npoints
        self.colorshelper = MplColorHelper("Greens", 0, self.rmax+self.rmax/4, inverse=True)

    @staticmethod
    def clean_axes(f=None):
        sns.despine(fig=f, offset=10, trim=False, left=False, right=True)

    def get_arr_idx(self, x,):
        # get the index in the value closest to x
        return np.int(x*self.npoints / self.rmax)

    def calc_variance(self, d):
        # gives the scale of the normal distribution used to represent path lengths
        return math.sqrt(d)*self.sigma_scaling

    def calc_maze_pr(self, l, r):
        ldist, _, _ = get_parametric_distribution("normal", loc=l, scale=self.calc_variance(l))
        rdist, _, _ = get_parametric_distribution("normal", loc=r, scale=self.calc_variance(r))

        mu = ldist.mean() - rdist.mean()
        sigma = ldist.std() + rdist.std()
        phi = stats.norm.cdf(-mu / sigma)

        return 1 - phi

    def calc_probs(self):
        # Calc p(R) for each maze given the current settings
        for maze, arm in self.mazes.items():
            self.model_prs[maze] = self.calc_maze_pr(arm.l, arm.r)

    def get_probs_delta(self):
        # compute the squared error in pR estimated of the model
        return np.sum([(self.prs[maze]-self.model_prs[maze])**2 for maze in self.mazes.keys()])

    def test_gradient(self):
        x = np.arange(0.0001, 100, .1)

        y = np.zeros_like(x).astype(np.float32)
        for i, p in enumerate(x):
            self.sigma_scaling = p
            self.calc_probs()
            y[i] = self.get_probs_delta()

        min_x, min_y = x[np.argmin(y)], np.min(y)

        f, ax = create_figure(subplots=False)
        ax.scatter(x, y)
        ax.scatter(min_x, min_y, color=red, s=200)
        print("min {} - {}".format(round(min_x, 4), round(min_y, 5)))


    def fit_sigma(self):
        self.minimize_record = [[], []] # store param and error at each iter of minimize
        def func(fact):
            self.sigma_scaling = fact[0]
            self.calc_probs()
            return self.get_probs_delta()

        def record(params):
            self.minimize_record[0].append(params[0])
            self.minimize_record[1].append(self.get_probs_delta())
            return True

        res = minimize(func, [10], callback=record, options=dict(disp=True), bounds=[[0.00001, 50]])

        print(res)
        return res


    def plot_distances_distributions(self):
        f, ax = create_figure(subplots=False)

        for d,c in zip(self.pathlengths, self.colors):
            plot_distribution(d, self.calc_variance(d), dist_type="normal", ax=ax, x_range=[0, 1000], shaded=True, 
                                plot_kwargs=dict(color=c, lw=5))
        ax.set(xlim=[0, 1000])

    
    def calc_utility_space(self, plot=False):
        x, y = np.meshgrid(a.L, a.R)
        mu = y- x
        sigma = np.array([a.calc_variance(xx) + a.calc_variance(yy) for xx,yy in zip(x.flat, y.flat)]).reshape(mu.shape)
        phi = stats.norm.cdf(-mu / sigma)
        self.us_prs = 1 - phi
    
        if plot:
            f, ax = create_figure(subplots=False)

            surf = ax.imshow(self.us_prs, extent=[0, self.rmax, 0, self.rmax], cmap=cm.coolwarm, origin="lower", aspect="equal", vmin=0, vmax=1)
            divider = make_axes_locatable(ax)
            cax1 = divider.append_axes("right", size="5%", pad=0.15)
            f.colorbar(surf, cax=cax1)

            ax.set(title="$p(R)$", xlabel="$R$", ylabel="$L$", xticks=[0, self.rmax], yticks=[0, self.rmax])
            
            self.clean_axes()

    def plot_slices(self):
        f, axarr = create_figure(subplots=True, ncols=3, nrows=1)

        self.calc_utility_space(plot=False)
        surf = axarr[0].imshow(self.us_prs, extent=[0, self.rmax, 0, self.rmax], cmap=cm.coolwarm, origin="lower", aspect="equal", vmin=0, vmax=1)

        eval_values = np.arange(100, self.rmax, 100)
        lslopes, rslopes = [], []
        for r0 in eval_values:
            r0idx = self.get_arr_idx(r0)
            color = self.colorshelper.get_rgb(r0)
            axarr[0].axvline(r0, color=color, lw=self.lw*.75, ls="--")
            axarr[0].axhline(r0, color=color, lw=self.lw*.75, ls="--")

            axarr[1].plot(self.us_prs[:, r0idx], color=color, lw=self.lw)
            axarr[2].plot(self.us_prs[r0idx, :], color=color, lw=self.lw)

        axarr[0].set(title="$p(R)$", xticks=[], yticks=[], xlabel="$R$", ylabel="$L$")
        axarr[1].set(title="$R\\ constant$",  xlabel="$L$", ylabel="$p(R)$", yticks=[0, round(np.nanmin(self.us_prs),2), round(np.nanmax(self.us_prs),2), 1], xticks=np.arange(0, self.npoints, np.int(250*self.points_conversion_factor)), xticklabels=np.arange(0, self.rmax+1, 100))
        axarr[2].set(title="$L\\ constant$",xlabel="$R$", ylabel="$p(R)$", yticks=[0, round(np.nanmin(self.us_prs),2), round(np.nanmax(self.us_prs),2), 1], xticks=np.arange(0, self.npoints, np.int(250*self.points_conversion_factor)), xticklabels=np.arange(0, self.rmax+1, 100))

        self.clean_axes(f=f)


    def plot_ICs(self):
        f, ax = create_figure(subplots=False)

        levels = np.arange(-.1, 1.11, .1)
        h = MplColorHelper("gray", -0., 2.11, inverse=False)
        colors = [h.get_rgb(l) for l in levels]

        contours = ax.contour(self.R, self.L, self.us_prs, levels=levels, colors=colors)
        ax.clabel(contours, inline=1, fontsize=10, colors=colors)
        ax.imshow(self.us_prs, extent=[0, self.rmax, 0, self.rmax], cmap=cm.coolwarm, origin="lower", aspect="equal", vmin=0, vmax=1)


#%%
# Compare contours of the two models
calc = PsiCalculator()
calc.getPsi()
calc.plot_slices()

a = Algomodel()
a.plot_slices()


f, axarr = create_figure(subplots=True, ncols=2)
levels = np.arange(-.1, 1.11, .1)
h = MplColorHelper("gray", -0., 2.11, inverse=False)
colors = [h.get_rgb(l) for l in levels]

contours = axarr[0].contour(calc.R, calc.L, calc.Psi, levels=levels, colors=colors)
axarr[0].clabel(contours, inline=1, fontsize=10, colors=colors)
axarr[0].imshow(calc.Psi, extent=[0, calc.rmax, 0, calc.rmax], cmap=cm.coolwarm, origin="lower", aspect="equal", vmin=0, vmax=1)

contours = axarr[1].contour(a.R, a.L, a.us_prs, levels=levels, colors=colors)
axarr[1].clabel(contours, inline=1, fontsize=10, colors=colors)
axarr[1].imshow(a.us_prs, extent=[0, a.rmax, 0, a.rmax], cmap=cm.coolwarm, origin="lower", aspect="equal", vmin=0, vmax=1)


titles = ["Psi", "Normal"]
for ax, t in zip(axarr, titles):
    ax.set(title=t)


#%%
