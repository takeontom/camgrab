import urllib.request
from datetime import datetime
from io import BytesIO
from os import makedirs
from os.path import dirname
from socket import timeout
from time import sleep
from urllib.error import HTTPError, URLError
import re

from PIL import Image
from PIL import ImageFile

# High chance of getting slightly corrupted images from a webcam stream, so
# make sure Pillow is being tolerant of this. Avoids èrrors like:
# ``OSError: image file is truncated (30 bytes not processed)``.
# https://stackoverflow.com/a/23575424
ImageFile.LOAD_TRUNCATED_IMAGES = True


def get_image_from_url(url, grabber):
    """Attempt to get an image from the supplied URL.

    Args:
        url: The full URL to attempt to grab the image from.

    Returns:
        PIL.Image.Image: The downloaded image as a Pillow Image.
    """
    response = urllib.request.urlopen(url, timeout=grabber.timeout)
    fp = BytesIO(response.read())
    im = Image.open(fp)
    return im


def do_save_image(result, grabber):
    """Save the supplied image to the filesystem.

    Args:
        im (PIL.Image.Image): The Pillow Image to save.
    """
    result['save_dir'] = grabber.save_dir
    result['save_path'] = grabber.get_save_path()
    result['save_path_full'] = grabber.format_path(result['save_path'], result)
    result['is_saved'] = False

    if not result.get('image', False):
        return result

    if grabber.should_save_image():
        grabber.make_save_path_dirs(result['save_path_full'])
        result['image'].save(result['save_path_full'])
        result['is_saved'] = True

    return result


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

        save_dir: The root directory to save images to. Can be a directory
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

        ignore_timeout: Whether timeout errors should be ignored. Default: True

        ignore_403: Whether HTTP 403 errors should be ignored. Default: False
        ignore_404: Whether HTTP 404 errors should be ignored. Default: False
        ignore_500: Whether HTTP 500 errors should be ignored. Default: True
    """

    def __init__(
        self,
        url,
        every=2,
        save_dir='grabbed_images',
        download_callable=None,
        extra_result_handlers=None
    ):
        self.url = url
        self.every = every
        self.save_dir = save_dir

        self.timeout = 30
        self.save_filename = '{Y}{m}{d}/{H}/{Y}{m}{d}-{H}{M}{S}-{f}.jpg'
        self.save = True

        self.download_callable = download_callable or get_image_from_url
        self.default_result_handlers = (do_save_image, )
        self.extra_result_handlers = extra_result_handlers or []
        self.result_handlers = None

        self.ignore_timeout = True
        self.ignore_403 = False
        self.ignore_404 = False
        self.ignore_500 = True

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
        request = self.create_request()
        result = self.download_image(request)
        self.handle_received_image(result)

    def create_request(self):
        request = {
            'url': self.url,
            'requested_at': datetime.now(),
        }
        return request

    def download_image(self, request):
        """Attempt to download an image from the grabber's URL.

        By default, this will attempt to use the built in
        ``get_image_from_url(url)`` method, however a different callable
        can be chosen by setting the grabber's ``downloader`` attribute.

        The callable used as the ``downloader`` must have the following
        signtature::

            def some_downloader(url):

        Returns:
            PIL.Image.Image: The downloaded image, or None if a squashed error
                was encountered.
        """
        url = request['url']
        download_callable = self.get_download_callable()

        result = request.copy()
        result['error'] = None

        im = None
        try:
            im = download_callable(url, self)
        except Exception as e:
            if not self.ignore_download_exception(e):
                raise e
            result['error'] = e

        result['image'] = im

        return result

    def get_download_callable(self):
        return self.download_callable

    def ignore_download_exception(self, e):
        def ignore_http_code(code):
            attribute = 'ignore_{}'.format(code)
            return getattr(self, attribute)

        # Basic socket timeout
        if isinstance(e, timeout):
            return self.ignore_timeout

        # socket timeout caught by urllib
        if isinstance(e, URLError):
            if isinstance(e.reason, timeout):
                return self.ignore_timeout

        # urllib HTTP errors
        if isinstance(e, HTTPError):
            return ignore_http_code(e.code)

        return False

    def handle_received_image(self, result):
        """Process the supplied image as per the grabber's configuration.

        Args:
            result (dict): The grabbed cam image, with meta information, to be
                processed.
        """
        for handler in self.get_result_handlers():
            result = handler(result, self)
        return result

    def get_result_handlers(self):
        if self.result_handlers:
            return self.result_handlers

        default = tuple(self.default_result_handlers or ())
        extra = tuple(self.extra_result_handlers or ())

        return default + extra

    def should_save_image(self):
        """Check whether the Grabber is configured to save images.

        Image saving can be toggled off by setting the ``save``,
        ``save_filename`` or ``save_dir`` attributes to None.

        Returns:
            bool: Whether the Grabber will attempt to save images or not.
        """
        return bool(self.save and self.save_filename and self.save_dir)

    def get_save_path(self):
        save_path = '{save_dir}/{save_filename}'.format(
            save_dir=self.save_dir, save_filename=self.save_filename
        )
        return save_path

    def make_save_path_dirs(self, save_path):
        """Create the directory and parent directories for the given path.

        Expects the path to include the filename.

        Args:
            save_path: The path, including the filename, to create the
                directories for.
        """
        dirs = dirname(save_path)
        makedirs(dirs, exist_ok=True)

    def format_path(self, path, request):
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
        now = request['requested_at']

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

            # More from request
            url=self.slugify(request['url']),
        )
        return out

    def slugify(self, value):
        # Just a slightly modified version of Django's slugify:
        # https://docs.djangoproject.com/en/1.11/_modules/django/utils/text/#slugify
        value = re.sub(r'[^\w\s-]', '-', value).strip().lower()
        return re.sub(r'[-\s]+', '-', value)
