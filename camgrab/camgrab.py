from datetime import datetime
from time import sleep
from os import makedirs
from os.path import dirname
import urllib.request
from PIL import Image
from io import BytesIO


class Grabber(object):

    def __init__(self, url, every=2, save_to='grabbed_images', send_to_callable=None):
        self.url = url
        self.every = every
        self.save_to = save_to
        self.send_to_callable = send_to_callable

        self.timeout = 30
        self.save_filename = '{Y}-{m}{d}/{H}/{y}{m}{d}-{H}{M}{S}-{f}.jpg'
        self.save = True

        # Will bail after running this many ticks
        self._test_max_ticks = None

    def begin(self):
        counter = 0
        while True and (self._test_max_ticks is None or counter < self._test_max_ticks):
            self.tick()
            sleep(self.every)
            if self._test_max_ticks:
                counter += 1

    def tick(self):
        try:
            im = self.get_image_from_url(self.url)
            self.handle_received_image(im)
        except Exception as e:
            raise e

    def get_image_from_url(self, url):
        """Attempt to get an image from the supplied URL.

        Returns a Pillow Image instance.
        """
        request = urllib.request.urlopen(self.url, timeout=self.timeout)
        fp = BytesIO(request.read())
        im = Image.open(fp)
        return im

    def handle_received_image(self, im):
        saved = False
        if self.should_save_image():
            saved = self.do_save_image(im)

        if self.send_to_callable:
            meta = {
                'saved': saved,
            }
            self.send_to_callable(im, **meta)

    def should_save_image(self):
        """Check whether the Grabber is configured to save images."""
        return bool(self.save and self.save_filename and self.save_to)

    def do_save_image(self, im):
        full_save_path = self.get_full_save_path()
        self.make_save_path_dirs(full_save_path)
        im.save(full_save_path)

    def get_full_save_path(self):
        save_full_path_raw = '{save_to}/{save_filename}'.format(
            save_to=self.save_to, save_filename=self.save_filename
        )
        save_full_path = self.format_path(save_full_path_raw)
        return save_full_path

    def make_save_path_dirs(self, save_path):
        """Create the directory and parent directories for the given path.

        Expects the path to include the filename.
        """
        dirs = dirname(save_path)
        makedirs(dirs, exist_ok=True)

    def format_path(self, path):
        now = datetime.now()

        out = path.format(
            Y=now.strftime('%Y'),
            y=now.strftime('%y'),
            m=now.strftime('%m'),
            d=now.strftime('%d'),
            H=now.strftime('%H'),
            M=now.strftime('%M'),
            S=now.strftime('%S'),
            f=now.strftime('%f'),
        )

        return out
