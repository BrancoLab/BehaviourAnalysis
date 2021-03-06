import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
import cv2 


def plot_fitted_curve(func, xdata, ydata, ax, xrange=None, print_fit=False, numpy_polyfit=False,
                        fit_kwargs={}, scatter_kwargs={}, line_kwargs={}):
    if numpy_polyfit and not isinstance(numpy_polyfit, int): raise ValueError("numpy_polyfit should be an integer")
    # set numpy_polifit to an integer to fit a numpy polinomial with degree numpy polyfit

    if xrange is not None: x = np.linspace(xrange[0], xrange[1], 100)
    else: x = np.linspace(np.min(xdata), np.max(xdata), 100)

    if not numpy_polyfit: # ? scipy curve fit instead
        popt, pcov = curve_fit(func, xdata, ydata, **fit_kwargs)
        if print_fit: print(popt)
        y = func(x, *popt)
        to_return = popt
    else:
        func = func(numpy_polyfit, xdata, ydata)
        y = func(x)
        to_return = func

    ax.scatter(xdata, ydata, **scatter_kwargs)
    ax.plot(x, y, **line_kwargs)

    return to_return

def opencv_write_clip(videopath, frames_data, w=None, h=None, framerate=None, start=None, stop=None,
                        format='.mp4', iscolor=False):
    """ create a .cv2 videowriter and  write clip to file """
    if format != '.mp4':
        raise ValueError('Fileformat not yet supported by this function: {}'.format(format))

    if start is None: start = 0
    if stop is None: stop = frames_data.shape[-1]
    start, stop = int(start), int(stop)
    if w is None: w = frames_data.shape[0]
    if h is None: h = frames_data.shape[1]
    if framerate is None: raise ValueError('No frame rate parameter was given as an input')

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    videowriter = cv2.VideoWriter(videopath, fourcc, framerate, (w, h), iscolor)

    for framen in range(start, stop):
        frame = np.array(frames_data[:, :, framen], dtype=np.uint8).T
        cv2.imshow('frame', frame)
        cv2.waitKey(1)
        videowriter.write(frame)
    videowriter.release()

def exponential(x, a, b, c, d):
    return  a*np.exp(-c*(x-b))+d

pink     = [.7, .4, .5]
teal     = [0., .7, .7]

# ? Create a video with a non linear loom
# * params
fps = 40

# Define a bunch of durations as number of frames
duration        = 5*fps  # total clip duration
still_dur       = 1*fps   # fixed spot at start of video
expansion       = int(.15*fps)   # loom expansion
expanded_dur    = int(1*fps)   # fixed expanded spot at end of video

# Define position and size
pos = (600, 400)  # position of stim on frame
size = (50, 400)  # Radius in pixels of the stim, start -> end
frame_size = (800, 1200)  # frame size in pixels, x and y are inverted because cv2

# Compute radius profile steps
# halway through the expansion (midt) the spot will have expanded to 10% of the final size
midt = int(expansion / 2)  # halftime of expansionduraiton
midt_size = (size[1]-size[0]) * .1 + size[0]


# * Show radius profile
# Plot radius profile
f, ax = plt.subplots()

xdata = [still_dur-5, still_dur, still_dur + midt, expansion+still_dur]
ydata = [size[0], size[0], midt_size, size[1]]

# Fit an exponential to the radius/time data to show the radius frame
# ! the fitted exponential is used to compute the radius during frames generation

popt = plot_fitted_curve(
    exponential, xdata, ydata, ax=ax, numpy_polyfit=False, xrange=[0, duration],
    fit_kwargs=dict(p0=(100, 40, .0001, 0)),
    scatter_kwargs={"color":pink, "s": 500}, 
    line_kwargs={"color": teal, "lw":3}
)

ax.set(xlabel="frame number", ylabel="spot size (px)", xlim=[0-5, still_dur+expansion+expanded_dur+5], ylim=[size[0]-10, size[1]+10])

# * Create frames
frames = np.ones((frame_size[0], frame_size[1], duration)).astype(np.uint8)
radiuses = []
for framen in np.arange(duration):
    # Get radius
    if framen <= still_dur:
        radius = size[0]
    elif framen > still_dur and framen <= still_dur + expansion:
        radius = int(exponential(framen, *popt))
    else:
        pass # Keep the last radius
    radiuses.append(radius)
    # Get frame and draw circle
    print("Frame: {} - radius: {}".format(framen, radius))
    frame = np.ones(frame_size, np.uint8) * 255 
    cv2.circle(frame, pos, radius, (0,0,0), -1)  # black circle yay

    frames[:, :, framen]  = frame

    cv2.imshow("frame", frame)
    cv2.waitKey(1)

ax.plot(radiuses, color="r", lw=3)
plt.show()

# ? Save video to file
videoname = "/Users/federicoclaudi/Dropbox (UCL - SWC)/Rotation_vte/plots/forT/kidsloom_3x.mp4"
opencv_write_clip(videoname, np.rot90(frames), w=frame_size[1], h=frame_size[0], framerate=fps,
                        format='.mp4', iscolor=False)
