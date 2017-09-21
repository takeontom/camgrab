import re
import socket
import urllib.request
from datetime import datetime
from io import BytesIO
from os import makedirs
from os.path import dirname
from time import sleep
from urllib.error import HTTPError, URLError

from PIL import Image, ImageFile

# High chance of getting slightly corrupted images from a webcam stream, so
# make sure Pillow is being tolerant of this. Avoids èrrors like:
# `OSError: image file is truncated (30 bytes not processed)`.
# https://stackoverflow.com/a/23575424
ImageFile.LOAD_TRUNCATED_IMAGES = True


def get_image_from_url(url, grabber):
    """Attempt to get an image from the supplied URL.

    Is a bare-minimum download handler to get images from static urls which
    will return an `image/jpeg` reponse.

    Args:
        url (str): The full URL to attempt to grab the image from.
        grabber (camgrab.Grabber): A Grabber instance, used to get settings,
            etc. from.

    Returns:
        PIL.Image.Image: The downloaded image as a Pillow Image.
    """
    response = urllib.request.urlopen(url, timeout=grabber.timeout)
    fp = BytesIO(response.read())

    # TODO: What error handling is needed here?
    im = Image.open(fp)
    return im


def do_save_image(result, grabber):
    """Result handler to save a result to the system.

    Modifies the supplied result dict with:

        * ``save_dir`` = the root directory for saving images
        * ``save_path`` = the configured path for saving images
        * ``save_path_full`` = the full path, token filtered
        * ``is_saved`` = whether the image has actually been saved or not

    Args:
        result (dict): A result dict to process.
        grabber (camgrab.Grabber): A Grabber instanced, used to get setings,
            etc. from.
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

            If using the default (``get_image_from_url()``) download handler,
            it is important the URL is to an actual image (i.e. responds with a
            ``image/jpeg`` content type), not a HTML page displaying or linking
            to the image.

            Only webcams which provide images in JPG format are currently
            supported by the default downloader. If you need more advanced
            functionality, then perhaps write a downloader and pass it to the
            grabber using the ``download_callable`` attribute.

        every: Default = ``2``

            The number of seconds to wait between each attempt at grabbing
            an image. Floats are fine for the number of seconds, so `0.2` will
            attempt to grab an image 5 times a second.

        download_callable: Default = ``get_image_from_url``

            A callable to use for the image downloading. By
            default will use the ``get_image_from_url`` download handler, which
            handles getting images from a simple URL.

            If a different callable is used, it must use the following
            signature::

                def some_callable(url, grabber)

        default_result_handlers: Default = ``(do_save_image, )``

            An iterable of result handlers to use by default. Extra result
            handlers can be set by using the ``extra_result_handlers``
            attribute. Or the result handlers to use can be fully set using
            the ``result_handlers`` attribute.

            If the ``result_handlers`` attribute is set, the
            ``default_result_handlers`` and ``extra_result_handlers``
            attributes will be ignored.

        extra_result_handlers: Default = ``[]``

            A list of extra result handlers to include when processing results.

            If the ``result_handlers`` attribute is set, the
            ``default_result_handlers`` and ``extra_result_handlers``
            attributes will be ignored.

        result_handlers: Default = None

            When set to an iterable of result handlers, will be used in
            preference to the ``default_result_handlers`` and
            ``extra_result_handlers`` attributes, allowing an easy way to
            specify completely which handlers to use.

        save_dir: Default = ``grabbed_images``

            The root directory to save images to. Can be a directory
            relative to the current project, or an absolute path to anywhere
            on the system.

            If the directory does not exist, an attempt will be made to create
            the directory.

            Setting to `None` will prevent images from being saved.

            Supports various tokens for making dynamic directories as needed,
            see below for more information.

        save_filename: Default = ``{Y}{m}{d}/{H}/{Y}{m}{d}-{H}{M}{S}-{f}.jpg``

            The filename to use for each downloaded image.

            Supports various tokens for making dynamic directories as needed,
            see below for more information.

        save: Default = ``True``

            Toggle the actual saving of each downloaded image. Useful when
            using the `send_to_callable` feature to only save images which
            defined by another algorithm. For example, to only save images
            if motion has been detected.

            This setting is dependant upon any result handlers respecting
            the setting.

        timeout: Default = ``30``

            The number of seconds to wait before timing out a connection to a
            webcam.

        ignore_timeout: Default = ``True``

            Whether timeout errors should be ignored.

        ignore_network: Default: ``True``

            Should general network errors (DNS, network unreachable, etc.) be
            ignored?

        ignore_xxx: Default: False

            Whether errors from specific HTTP status codes should be ignored.

            By default, the following are ignored: 500

            When not ignored, HTTP errors will need to be handled (or not) by
            consuming code.

        failed_exception: Default: None

            Set to the exception which causes the ``tick()`` method to crash.
            Is useful for debugging in threaded setups.
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

        self.download_callable = download_callable or get_image_from_url

        self.default_result_handlers = (do_save_image, )
        self.extra_result_handlers = extra_result_handlers or []
        self.result_handlers = None

        self.save_dir = save_dir
        self.save_filename = '{Y}{m}{d}/{H}/{Y}{m}{d}-{H}{M}{S}-{f}.jpg'
        self.save = True

        self.timeout = 30

        self.ignore_timeout = True
        self.ignore_network = True

        self.failed_exception = None

        ignore_status_codes = (
            307, 400, 408, 409, 429, 444, 451, 499, 500, 502, 503, 504, 507,
            599
        )

        for code in ignore_status_codes:
            setattr(self, 'ignore_{}'.format(code), True)

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
                # Let's not incrememt the counter unless it's needed.
                counter += 1

    def tick(self):
        """Instructs the grabber to perform a single "tick".

        Each tick does 2 simple things:

            1) Attempt to download an image
            2) Attempt to process the result

        It's safe to call ``tick()`` from consuming code, allowing easy
        replacement of the ``begin()`` method, if needed.

        If any unhndled exceptions are raised during the tick, then the
        `failed_exception` attribute is set with the exception. This allows
        for retrospective inspection of why a Grabber failed in threaded
        setups.
        """
        try:
            request = self.create_request()
            result = self.download_image(request)
            self.handle_received_image(result)
        except Exception as e:
            self.failed_exception = e
            raise e

    def create_request(self):
        """Create the request dict to be used by download handlers.

        The request dict which can be used to pass common information to the
        download handler, ensuring the same "now" datetime is used throughout
        the process.

        Returns:
            dict
        """
        request = {
            'url': self.url,
            'requested_at': datetime.now(),
        }
        return request

    def download_image(self, request):
        """Attempt to download an image from the grabber's URL.

        By default, this will attempt to use the built in
        ``get_image_from_url(url)`` method, however a different callable
        can be chosen by setting the grabber's ``download_callable`` attribute.

        The returned "result" dict contains the downloaded image (if download
        was successful), information about any errors, the requested URL, etc.,
        which should be enough for result handlers to do their thing.

        The callable used as the downloader must have the following
        signtature::

            def some_downloader(url, grabber):

        Args:
            dict: The "request" dictionary.

        Returns:
            dict: A "result" dictionary.
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
        """
        Returns:
            callable: The callable to use for the download request.
        """
        return self.download_callable

    def ignore_download_exception(self, e):
        """Check the Grabber's config to see whether the supplied exception
        should be ignored or not.

        Args:
            e (Exception): The exception to check

        Returns:
            bool: ``True`` to ignore, ``False`` otherwise.
        """
        # Basic socket timeout
        if isinstance(e, socket.timeout):
            return self.ignore_timeout

        # socket timeout caught by urllib
        if isinstance(e, URLError):
            if isinstance(e.reason, socket.timeout):
                return self.ignore_timeout
            if isinstance(e.reason, socket.gaierror):
                return self.ignore_network
            if isinstance(e.reason, OSError):
                return self.ignore_network
            else:
                print(e.reason)

        # urllib HTTP errors
        if isinstance(e, HTTPError):
            return self.ignore_http_code(e.code)

        return False

    def ignore_http_code(self, code):
        attribute = 'ignore_{}'.format(code)
        return getattr(self, attribute, False)

    def handle_received_image(self, result):
        """Process the supplied "result" dict.

        Each configured result handler will be called in turn. Result handlers
        may return a modified result dict, which will then be passed to the
        next result handler. Allows for complex behaviour to be chained
        together.

        Args:
            result (dict): The "result" dict

        Returns:
            dict: The final result dict.
        """
        for handler in self.get_result_handlers():
            result = handler(result, self) or result
        return result

    def get_result_handlers(self):
        """Get an iterable of all the configured result handlers.

        Returns:
            tuple: A tuple of result handlers.
        """
        if self.result_handlers:
            return self.result_handlers

        default = tuple(self.default_result_handlers or ())
        extra = tuple(self.extra_result_handlers or ())

        return default + extra

    def should_save_image(self):
        # TODO: handle all this in do_save_image handler instead of here
        return bool(self.save and self.save_filename and self.save_dir)

    def get_save_path(self):
        """Returns the base directory and filename of where to save images.

        If the configured directory or filename have tokens (which is likely),
        then the result will include the tokens and will need to be ran through
        ``format_path()`` before being used.

        Is a method just for convenience, and result handlers may use their own
        method of getting save locations.

        Returns:
            str: The configured ``save_dir`` and ``save_filename`` attributes.
        """
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

    def format_path(self, path, data):
        """Token filter the supplied path.

        Available tokens:

            * All the standard strftime directives found here:
                https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior
            * url: The requested URL, with illegal path characters cleaned out.

        The token filtering is performed by str.format(), so the tokens in the
        path should be wrapped in curly braces, for example::

            'some_dir/{Y}/{m}/{d}/{url}/{H}{M}{S}.jpg'

        Args:
            path (str): A string ready to be token filtered.
            data (dict): A "request" or "result" dict, the values of which
                will be used for the formatting.

        Returns:
            str: The token filtered path.
        """
        now = data['requested_at']

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
            url=self.slugify(data['url']),
        )
        return out

    def slugify(self, value):
        """Slugify the provided value to make it safe to use in paths.

        Replaces problematic characters with hyphens.

        Args:
            value (str): The string to slugify.

        Returns:
            str: The supplied string made safe for paths.
        """
        # Just a slightly modified version of Django's slugify:
        # https://docs.djangoproject.com/en/1.11/_modules/django/utils/text/#slugify
        value = re.sub(r'[^\w\s-]', '-', value).strip().lower()
        return re.sub(r'[-\s]+', '-', value)
