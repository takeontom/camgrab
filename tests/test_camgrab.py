import os
import httpretty
import pytest
from camgrab.camgrab import Grabber
from datetime import datetime

from PIL.Image import Image


class TestGrabber(object):

    def test_init(self):
        url = 'http://example.com'
        grabber = Grabber(url)

        assert grabber.url == url
        assert grabber.every == 2
        assert grabber.save_to == 'grabbed_images'
        assert grabber.send_to_callable is None

        kwargs = {
            'url': url,
            'every': 0.5,
            'save_to': 'somewhere_else',
            'send_to_callable': lambda x: x,
        }

        grabber = Grabber(**kwargs)
        for key, value in kwargs.items():
            assert getattr(grabber, key) == value

    def test_begin(self, mocker):
        grabber = Grabber('http://example.com')
        grabber._test_max_ticks = 5

        grabber.every = 13

        grabber.tick = mocker.Mock(grabber.tick, autospec=True)
        mocked_sleep = mocker.patch('camgrab.camgrab.sleep', autospec=True)

        grabber.begin()

        grabber.tick.assert_call_count = 5
        mocked_sleep.assert_call_count = 5
        mocked_sleep.assert_called_with(13)

    def test_tick(self, mocker):
        url = 'http://example.com'
        im = Image()

        grabber = Grabber(url)

        grabber.get_image_from_url = mocker.Mock(
            grabber.get_image_from_url, autospec=True, return_value=im
        )
        grabber.handle_received_image = mocker.Mock(
            grabber.handle_received_image, autospec=True
        )

        grabber.tick()

        grabber.get_image_from_url.assert_called_once_with(url)
        grabber.handle_received_image.assert_called_once_with(im)

    @httpretty.activate
    def test_get_image_from_url(self, mocker):
        dummy_url = 'http://a-url.com/'
        dummy_timeout = 123
        dummy_image_path = os.path.join(
            os.path.dirname(__file__), 'assets', 'kitty.jpg'
        )
        dummy_body = open(dummy_image_path, 'rb').read()

        httpretty.register_uri(
            httpretty.GET, dummy_url,
            body=dummy_body, content_type='image/jpeg'
        )

        grabber = Grabber('http://example.com')
        grabber.timeout = dummy_timeout

        grabber.get_image_from_url(dummy_url)

    def test_handle_received_image(self, mocker):
        grabber = Grabber('http://example.com')
        im = Image()

        grabber.do_save_image = mocker.Mock(
            grabber.do_save_image, autospec=True, return_value=True
        )
        grabber.do_send_to_callable = mocker.Mock(
            grabber.do_send_to_callable, autospec=True, return_value=True
        )

        dummy_meta = {
            'saved': True,
            'other_meta': 'some value',
        }
        grabber.generate_meta = mocker.Mock(
            grabber.generate_meta, autospec=True, return_value=dummy_meta
        )

        # Shouldn't save or send to callable
        grabber.should_save_image = mocker.Mock(
            grabber.should_save_image, autospec=True, return_value=False
        )
        grabber.send_to_callable = None
        grabber.handle_received_image(im)
        grabber.should_save_image.assert_called_once_with()
        grabber.do_save_image.assert_not_called()
        grabber.do_send_to_callable.assert_not_called()

        # Should save, but not send to callable
        grabber.should_save_image = mocker.Mock(
            grabber.should_save_image, autospec=True, return_value=True
        )
        grabber.handle_received_image(im)
        grabber.should_save_image.assert_called_once_with()
        grabber.do_save_image.assert_called_once_with(im)
        grabber.do_send_to_callable.assert_not_called()

        # Don't save, but do send to callable
        grabber.should_save_image = mocker.Mock(
            grabber.should_save_image, autospec=True, return_value=False
        )
        grabber.do_save_image = mocker.Mock(
            grabber.do_save_image, autospec=True, return_value=True
        )
        grabber.send_to_callable = lambda x: x
        grabber.handle_received_image(im)
        grabber.should_save_image.assert_called_once_with()
        grabber.do_save_image.assert_not_called()
        grabber.do_send_to_callable.assert_called_with(im, **dummy_meta)

    def test_should_save_image(self):
        good_grabber = Grabber('http://example.com')

        good_grabber.save = True
        good_grabber.save_filename = 'some_filename'
        good_grabber.save_to = 'some_dir'
        assert good_grabber.should_save_image() is True

        no_save_grabber = Grabber('http://example.com')
        no_save_filename_grabber = Grabber('http://example.com')
        no_save_dir_grabber = Grabber('http://example.com')

        no_save_grabber.save = False
        no_save_grabber.save_filename = 'some_filename'
        no_save_grabber.save_to = 'some_dir'

        no_save_filename_grabber.save = True
        no_save_filename_grabber.save_filename = None
        no_save_filename_grabber.save_to = 'some_dir'

        no_save_dir_grabber.save = True
        no_save_dir_grabber.save_filename = 'some_filename'
        no_save_dir_grabber.save_to = None

        bad_grabbers = (
            no_save_grabber, no_save_dir_grabber, no_save_filename_grabber
        )
        for grabber in bad_grabbers:
            assert grabber.should_save_image() is False

    def test_do_save_image(self, mocker):
        grabber = Grabber('http://example.com')

        im = Image()
        im.save = mocker.Mock(im.save, autospec=True)

        dummy_save_path = 'some/save/path.jpg'
        grabber.get_full_save_path = mocker.Mock(
            grabber.get_full_save_path, autospec=True,
            return_value=dummy_save_path
        )

        grabber.make_save_path_dirs = mocker.Mock(
            grabber.make_save_path_dirs, autospec=True
        )

        grabber.do_save_image(im)

        grabber.get_full_save_path.assert_called_once_with()
        grabber.make_save_path_dirs.assert_called_once_with(dummy_save_path)
        im.save.assert_called_once_with(dummy_save_path)

    def test_generate_meta(self):
        expected = {
            'saved': True,
        }

        grabber = Grabber('http://example.com')
        assert grabber.generate_meta(saved=True) == expected

    def test_do_send_to_callable(self, mocker):
        im = Image()
        grabber = Grabber('http://example.com')
        grabber.send_to_callable = None

        with pytest.raises(TypeError):
            grabber.do_send_to_callable(im, saved=True)

        grabber.send_to_callable = mocker.Mock()

        grabber.do_send_to_callable(im, saved=True)

        grabber.send_to_callable.assert_called_once_with(
            im, saved=True
        )

    def test_create_save_path_dirs(self, mocker):
        mocked_makedirs = mocker.patch('camgrab.camgrab.makedirs')
        path = 'a_dir/somewhere/another_dir/final_file.jpg'

        grabber = Grabber('http://example.com')

        grabber.make_save_path_dirs(path)

        mocked_makedirs.assert_called_once_with(
            'a_dir/somewhere/another_dir', exist_ok=True
        )

    def test_get_full_save_path(self, mocker):
        mocked_datetime = mocker.patch(
            'camgrab.camgrab.datetime', autospec=True
        )
        fake_datetime = datetime(2017, 1, 2, 12, 13, 14, 987654)
        mocked_datetime.now = mocker.Mock(return_value=fake_datetime)

        grabber = Grabber('http://example.com')
        grabber.save_to = 'a_dir'
        grabber.save_filename = '{Y}{m}{d}/blah/{H}{M}{S}{f}.jpg'

        expected = 'a_dir/20170102/blah/121314987654.jpg'

        grabber.format_path = mocker.Mock(
            grabber.format_path, autospec=True, return_value=expected
        )

        full_save_path = grabber.get_full_save_path()
        assert full_save_path == expected
        grabber.format_path.assert_called_once_with('a_dir/{Y}{m}{d}/blah/{H}{M}{S}{f}.jpg')

    def test_format_path(self, mocker):
        mocked_datetime = mocker.patch(
            'camgrab.camgrab.datetime', autospec=True
        )
        fake_datetime = datetime(2017, 1, 2, 12, 13, 14, 987654)
        mocked_datetime.now = mocker.Mock(return_value=fake_datetime)

        path = 'some_dir/{Y}-{m}-{d}/{y}{m}{d}-{H}{M}{S}-{f}.jpg'
        expected = 'some_dir/2017-01-02/170102-121314-987654.jpg'

        grabber = Grabber('http://example.com')
        result = grabber.format_path(path)
        assert result == expected