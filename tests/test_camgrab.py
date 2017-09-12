import os
from datetime import datetime

import httpretty
import pytest
from PIL.Image import Image

from camgrab.camgrab import Grabber


class TestGrabber(object):
    def test_init(self):
        url = 'http://example.com'
        grabber = Grabber(url)

        assert grabber.url == url
        assert grabber.every == 2
        assert grabber.save_to == 'grabbed_images'
        assert grabber.send_to_callable is None
        assert grabber.download_callable is None

        kwargs = {
            'url': url,
            'every': 0.5,
            'save_to': 'somewhere_else',
            'send_to_callable': lambda x: x,
            'download_callable': lambda x: x,
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
        im = Image()

        grabber = Grabber('http://example.com')

        grabber.download_image = mocker.Mock(
            grabber.download_image, autospec=True, return_value=im
        )
        grabber.handle_received_image = mocker.Mock(
            grabber.handle_received_image, autospec=True
        )

        grabber.tick()

        grabber.download_image.assert_called_once_with()
        grabber.handle_received_image.assert_called_once_with(im)

    def test_download_image(self, mocker):
        im = Image()
        url = 'http://example.com'
        grabber = Grabber(url)

        grabber.get_image_from_url = mocker.Mock(
            grabber.get_image_from_url, autospec=True, return_value=im
        )

        result = grabber.download_image()

        grabber.get_image_from_url.assert_called_once_with(url)
        assert result is im

    def test_download_image__diff_downloader(self, mocker):
        im = Image()
        url = 'http://example.com'
        grabber = Grabber(url)

        mock_downloader = mocker.Mock(return_value=im)
        grabber.download_callable = mock_downloader

        grabber.get_image_from_url = mocker.Mock(
            grabber.get_image_from_url, autospec=True, return_value=im
        )

        result = grabber.download_image()

        grabber.get_image_from_url.assert_not_called()
        mock_downloader.assert_called_once_with(url)
        assert result is im

    @httpretty.activate
    def test_get_image_from_url(self):
        dummy_url = 'http://a-url.com/'
        dummy_timeout = 123
        dummy_image_path = os.path.join(
            os.path.dirname(__file__), 'assets', 'kitty.jpg'
        )
        dummy_body = open(dummy_image_path, 'rb').read()

        httpretty.register_uri(
            httpretty.GET,
            dummy_url,
            body=dummy_body,
            content_type='image/jpeg'
        )

        grabber = Grabber('http://example.com')
        grabber.timeout = dummy_timeout

        grabber.get_image_from_url(dummy_url)

    def test_handle_received_image__no_action(self, mocker):
        im = Image()

        dummy_meta = {
            'saved': True,
            'other_meta': 'some value',
        }

        grabber = Grabber('http://example.com')
        grabber.do_save_image = mocker.Mock(
            grabber.do_save_image, autospec=True, return_value=True
        )
        grabber.do_send_to_callable = mocker.Mock(
            grabber.do_send_to_callable, autospec=True, return_value=True
        )
        grabber.generate_meta = mocker.Mock(
            grabber.generate_meta, autospec=True, return_value=dummy_meta
        )
        grabber.should_save_image = mocker.Mock(
            grabber.should_save_image, autospec=True, return_value=False
        )
        grabber.send_to_callable = None

        grabber.handle_received_image(im)

        grabber.should_save_image.assert_called_once_with()
        grabber.do_save_image.assert_not_called()
        grabber.do_send_to_callable.assert_not_called()

    def test_handle_received_image__only_save(self, mocker):
        im = Image()

        dummy_meta = {
            'saved': True,
            'other_meta': 'some value',
        }

        grabber = Grabber('http://example.com')
        grabber.do_save_image = mocker.Mock(
            grabber.do_save_image, autospec=True, return_value=True
        )
        grabber.do_send_to_callable = mocker.Mock(
            grabber.do_send_to_callable, autospec=True, return_value=True
        )
        grabber.generate_meta = mocker.Mock(
            grabber.generate_meta, autospec=True, return_value=dummy_meta
        )
        grabber.should_save_image = mocker.Mock(
            grabber.should_save_image, autospec=True, return_value=True
        )
        grabber.send_to_callable = None

        grabber.handle_received_image(im)

        grabber.should_save_image.assert_called_once_with()
        grabber.do_save_image.assert_called_once_with(im)
        grabber.do_send_to_callable.assert_not_called()

    def test_handle_received_image__only_send_to_callable(self, mocker):
        im = Image()

        dummy_meta = {
            'saved': True,
            'other_meta': 'some value',
        }

        grabber = Grabber('http://example.com')

        grabber.do_save_image = mocker.Mock(
            grabber.do_save_image, autospec=True
        )
        grabber.do_send_to_callable = mocker.Mock(
            grabber.do_send_to_callable, autospec=True, return_value=True
        )
        grabber.generate_meta = mocker.Mock(
            grabber.generate_meta, autospec=True, return_value=dummy_meta
        )
        grabber.should_save_image = mocker.Mock(
            grabber.should_save_image, autospec=True, return_value=False
        )
        grabber.send_to_callable = lambda x: x

        grabber.handle_received_image(im)

        grabber.generate_meta.assert_called_once_with(False)
        grabber.should_save_image.assert_called_once_with()
        grabber.do_save_image.assert_not_called()
        grabber.do_send_to_callable.assert_called_with(
            grabber.send_to_callable, im, **dummy_meta
        )

    def test_handle_received_image__save_and_send_to_callable(self, mocker):
        im = Image()

        dummy_meta = {
            'saved': True,
            'other_meta': 'some value',
        }

        grabber = Grabber('http://example.com')

        grabber.do_save_image = mocker.Mock(
            grabber.do_save_image, autospec=True
        )
        grabber.do_send_to_callable = mocker.Mock(
            grabber.do_send_to_callable, autospec=True, return_value=True
        )
        grabber.generate_meta = mocker.Mock(
            grabber.generate_meta, autospec=True, return_value=dummy_meta
        )
        grabber.should_save_image = mocker.Mock(
            grabber.should_save_image, autospec=True, return_value=True
        )
        grabber.send_to_callable = lambda x: x

        grabber.handle_received_image(im)

        grabber.generate_meta.assert_called_once_with(True)
        grabber.should_save_image.assert_called_once_with()
        grabber.do_save_image.assert_called_once_with(im)
        grabber.do_send_to_callable.assert_called_with(
            grabber.send_to_callable, im, **dummy_meta
        )

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
            grabber.get_full_save_path,
            autospec=True,
            return_value=dummy_save_path
        )

        grabber.make_save_path_dirs = mocker.Mock(
            grabber.make_save_path_dirs, autospec=True
        )

        grabber.do_save_image(im)

        grabber.get_full_save_path.assert_called_once_with()
        grabber.make_save_path_dirs.assert_called_once_with(dummy_save_path)
        im.save.assert_called_once_with(dummy_save_path)

    def test_generate_meta(self, mocker):
        dummy_url = 'http://some-url.com'
        dummy_save_dir = '/some/save/dir'
        dummy_save_full_path = '/some/save/dir/2017-05-13/20170513-121314.jpg'
        dummy_now = datetime(2017, 5, 13, 12, 13, 14)

        mocked_datetime = mocker.patch(
            'camgrab.camgrab.datetime', autospec=True
        )
        mocked_datetime.now = mocker.Mock(return_value=dummy_now)

        expected = {
            'save_dir': dummy_save_dir,
            'save_full_path': dummy_save_full_path,
            'is_saved': True,
            'url': dummy_url,
            'now': dummy_now,
        }

        grabber = Grabber(dummy_url)
        grabber.save_to = dummy_save_dir
        grabber.save_filename = '{Y}-{m}-{d}/{Y}{m}{d}-{H}{M}{S}.jpg'
        assert grabber.generate_meta(saved=True) == expected

    def test_do_send_to_callable(self, mocker):
        im = Image()
        grabber = Grabber('http://example.com')

        with pytest.raises(TypeError):
            grabber.do_send_to_callable(None, im, saved=True)

        mock_callable = mocker.Mock()

        grabber.do_send_to_callable(mock_callable, im, saved=True)

        mock_callable.assert_called_once_with(im, saved=True)

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
        grabber.format_path.assert_called_once_with(
            'a_dir/{Y}{m}{d}/blah/{H}{M}{S}{f}.jpg'
        )

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
