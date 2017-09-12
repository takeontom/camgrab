import urllib.request
from datetime import datetime
from io import BytesIO
from os import makedirs
from os.path import dirname
from time import sleep

from PIL import Image


class Grabber(object):
    """Manages the downloading and processing of images from webcams.

    Designed to provide a simple base for grabbing images from webcams,
    allowing more complex and bespoke functionality to be added easily
    as needed.

    Attributes:
        url: The publically accessible URL for the webcam image, is likely
            going to be something like: `'http://78.100.133.169:8888/out.jpg'`.

            If using the default downloader, it is important the URL is to the
            actual image, not HTML page displaying or linking to the image.

            Only webcams which provide images in JPG format are currently
            supported by the default downloader. If you need more advanced
            functionality, then perhaps write a downloader and pass it to the
            grabber using the ``download_callable`` attribute.

        every: The number of seconds to wait between each attempt at grabbing
            an image. Floats are fine for the number of seconds, so `0.2` will
            attempt to grab an image 5 times a second.

        save_to: The root directory to save images to. Can be a directory
            relative to the current project, or an absolute path to anywhere
            on the system.

            If the directory does not exist, an attempt will be made to create
            the directory.

            Setting to `None` will prevent images from being saved.

            Supports various tokens for making dynamic directories as needed,
            see below for more information.

        timeout: The number of seconds to wait before timing out a connection
            to a webcam.

        save_filename: The filename to use for each downloaded image.

            Supports various tokens for making dynamic directories as needed,
            see below for more information.

        save: Toggle the actual saving of each downloaded image. Useful when
            using the `send_to_callable` feature to only save images which
            defined by another algorithm. For example, to only save images
            if motion has been detected.

            When set to ``False``, the _desired_ save location for an image
            is still passed to the callable in the meta information.

        download_callable: A callable to use for the image downloading. By
            default will use the ``get_image_from_url`` downloader, which
            handles getting images from a simple URL.

            If a different callable is used, it must use the following
            signature::

                def some_callable(url)

        send_to_callable: Optionally set to a callable, and the Grabber will
            pass each downloaded image (as a Pillow Image) and some meta
            information to the callable.

            The callable should have the following signature::

                def some_callable(im, **meta):
    """

    def __init__(
        self,
        url,
        every=2,
        save_to='grabbed_images',
        download_callable=None,
        send_to_callable=None
    ):
        self.url = url
        self.every = every
        self.save_to = save_to

        self.timeout = 30
        self.save_filename = '{Y}{m}{d}/{H}/{Y}{m}{d}-{H}{M}{S}-{f}.jpg'
        self.save = True

        self.send_to_callable = send_to_callable
        self.download_callable = download_callable

        # Will bail after running this many ticks
        self._test_max_ticks = None

    def begin(self):
        """Start grabbing images until stopped.

        The Grabber uses a simple ``sleep`` to wait the configured number of
        seconds between each tick, as configured by the ``every`` attribute.

        To use a different mechanism for delaying grabbing images, either
        override this method, or write a custom script to handle the timing,
        which then simply calls the grabber's ``tick()`` method.
        """

        def do_next_tick(counter):
            # Allows for easier testing.
            max_ticks = self._test_max_ticks
            return max_ticks is None or counter < max_ticks

        counter = 0

        while do_next_tick(counter):
            self.tick()
            sleep(self.every)
            if self._test_max_ticks:
                counter += 1

    def tick(self):
        """Instructs the grabber to perform a single "tick".

        Each tick does 2 simple things:

            1) Download an image
            2) Process the downloaded image
        """
        im = self.download_image()
        self.handle_received_image(im)

    def download_image(self):
        """Attempt to download an image from the grabber's URL.

        By default, this will attempt to use the built in
        ``get_image_from_url(url)`` method, however a different callable
        can be chosen by setting the grabber's ``downloader`` attribute.

        The callable used as the ``downloader`` must have the following
        signtature::

            def some_downloader(url):

        Returns:
            PIL.Image.Image: The downloaded image.
        """
        if self.download_callable:
            im = self.download_callable(self.url)
        else:
            im = self.get_image_from_url(self.url)
        return im

    def get_image_from_url(self, url):
        """Attempt to get an image from the supplied URL.

        Args:
            url: The full URL to attempt to grab the image from.

        Returns:
            PIL.Image.Image: The downloaded image as a Pillow Image.
        """
        response = urllib.request.urlopen(url, timeout=self.timeout)
        fp = BytesIO(response.read())
        im = Image.open(fp)
        return im

    def handle_received_image(self, im):
        """Process the supplied image as per the grabber's configuration.

        Args:
            im (PIL.Image.Image): The image to process as a Pillow Image.
        """
        saved = False
        if self.should_save_image():
            self.do_save_image(im)
            saved = True

        if self.send_to_callable:
            meta = self.generate_meta(saved)
            self.do_send_to_callable(self.send_to_callable, im, **meta)

    def generate_meta(self, saved):
        """Create a dict containing meta information about the camgrab tick.

        Args:
            saved (bool): Whether the image has been saved to the filesystem or
                not.

        Returns:
            dict: The generated meta data, e.g.::
                {
                    'is_saved': True,
                    'now': datetime.Datetime(),
                    'save_dir': 'some-save-dir',
                    'save_full_path': 'some-dir/images/20170102/141516.jpg',
                    'url': 'http://someurl.com',
                }
        """
        now = datetime.now()
        meta = {
            'is_saved': saved,
            'now': now,
            'save_dir': self.save_to,
            'save_full_path': self.get_full_save_path(),
            'url': self.url,
        }
        return meta

    def should_save_image(self):
        """Check whether the Grabber is configured to save images.

        Image saving can be toggled off by setting the ``save``,
        ``save_filename`` or ``save_to`` attributes to None.

        Returns:
            bool: Whether the Grabber will attempt to save images or not.
        """
        return bool(self.save and self.save_filename and self.save_to)

    def do_save_image(self, im):
        """Save the supplied image to the filesystem.

        Args:
            im (PIL.Image.Image): The Pillow Image to save.
        """
        full_save_path = self.get_full_save_path()
        self.make_save_path_dirs(full_save_path)
        im.save(full_save_path)

    def do_send_to_callable(self, the_callable, im, **meta):
        """
        Send the supplied image to the supplied callable.

        The callable should have the following signature::

            def some_callable(im, **meta):

        See `generate_meta`_ for details on the meta information passed to
        the callable.

        No attempt is made to handle any exceptions raised by the callable,
        so it is important the callable handles any likely exceptions itself.

        The call to the callable is a blocking call. Therefore, if the callable
        is going to perform lengthy operations, it is adviseable to implement
        some flavour of threading within the callable itself.

        Args:
            the_callable: Any Python callable.
            im (PIL.Image.Image): The Pillow Image to pass to the callable.
            **meta: Meta data to pass to the callable.
        """
        the_callable(im, **meta)

    def get_full_save_path(self):
        """Provide the full, token filtered, path to save the current to.

        The full save path is a concatenation of the ``save_to`` and
        ``save_filename`` attributes, which are then token filtered.

        See `format_path`_ for details on the token filtering.

        Returns:
            str: The full path to save the current image.
        """
        save_full_path_raw = '{save_to}/{save_filename}'.format(
            save_to=self.save_to, save_filename=self.save_filename
        )
        save_full_path = self.format_path(save_full_path_raw)
        return save_full_path

    def make_save_path_dirs(self, save_path):
        """Create the directory and parent directories for the given path.

        Expects the path to include the filename.

        Args:
            save_path: The path, including the filename, to create the
                directories for.
        """
        dirs = dirname(save_path)
        makedirs(dirs, exist_ok=True)

    def format_path(self, path):
        """Token filter the supplied path.

        Available tokens:

            * All the standard strftime directives found here:
                https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior

        The token filtering is performed by str.format(), so the path should
        be supplied looking something like::

            'some_dir/{Y}/{m}/{d}/{H}{M}{S}.jpg'

        Args:
            path: A string ready to be token filtered.

        Returns:
            str: The token filtered path.
        """
        now = datetime.now()

        out = path.format(
            # All the standard strftime directives:
            a=now.strftime('%a'),
            A=now.strftime('%A'),
            w=now.strftime('%w'),
            d=now.strftime('%d'),
            b=now.strftime('%b'),
            B=now.strftime('%B'),
            m=now.strftime('%m'),
            y=now.strftime('%y'),
            Y=now.strftime('%Y'),
            H=now.strftime('%H'),
            I=now.strftime('%I'),
            p=now.strftime('%p'),
            M=now.strftime('%M'),
            S=now.strftime('%S'),
            f=now.strftime('%f'),
            z=now.strftime('%z'),
            Z=now.strftime('%Z'),
            j=now.strftime('%j'),
            U=now.strftime('%U'),
            W=now.strftime('%W'),
            c=now.strftime('%c'),
            x=now.strftime('%x'),
            X=now.strftime('%X'),
        )
        return out
