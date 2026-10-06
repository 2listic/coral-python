from pde.visualization.movies import Movie


class PyPDEMovie:
    """Wrapper for a Movie.

    ``bitrate`` is not a Movie parameter — py-pde forwards unknown keywords to matplotlib's
    FFMpegWriter, which is where the bit rate is set. Constructing one raises ``RuntimeError``
    when the ffmpeg binary is missing, which is the right moment to find out.
    """

    def __init__(self, filename: str, framerate: int, dpi: int, bitrate: int):
        self.movie = Movie(filename, framerate=framerate, dpi=dpi, bitrate=bitrate)
