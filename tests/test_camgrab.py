import os
from datetime import datetime
from socket import timeout
from urllib.error import HTTPError

import httpretty
import pytest
from PIL import Image

from camgrab.camgrab import Grabber


class TestGrabber(object):
    def test_init(self):
        url = 'http://example.com'
        grabber = Grabber(url)

        # Default attribute values
        assert grabber.url == url
        assert grabber.every == 2
        assert grabber.save_dir == 'grabbed_images'
        assert grabber.download_callable is None
        assert grabber.default_result_handlers == (grabber.do_save_image, )
        assert grabber.extra_result_handlers == []
        assert grabber.result_handlers is None
        assert grabber.timeout == 30
        assert grabber.save_filename == (
            '{Y}{m}{d}/{H}/{Y}{m}{d}-{H}{M}{S}-{f}.jpg'
        )
        assert grabber.save is True

        assert grabber.ignore_timeout is True
        assert grabber.ignore_403 is False
        assert grabber.ignore_404 is False
        assert grabber.ignore_500 is True

        assert grabber._test_max_ticks is None

        kwargs = {
            'url': url,
            'every': 0.5,
            'save_dir': 'somewhere_else',
            'download_callable': lambda x: x,
            'extra_result_handlers': [lambda x: x],
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
        im = Image.Image()

        grabber = Grabber('http://example.com')

        dummy_result = {'image': im, 'requested_at': datetime.now()}

        grabber.download_image = mocker.Mock(
            grabber.download_image, autospec=True, return_value=dummy_result
        )
        grabber.handle_received_image = mocker.Mock(
            grabber.handle_received_image, autospec=True
        )

        grabber.tick()

        grabber.download_image.assert_called_once_with()
        grabber.handle_received_image.assert_called_once_with(dummy_result)

    def test_download_image(self, mocker):
        mocked_datetime = mocker.patch(
            'camgrab.camgrab.datetime', autospec=True
        )
        fake_datetime = datetime(2017, 1, 2, 12, 13, 14, 987654)
        mocked_datetime.now = mocker.Mock(return_value=fake_datetime)

        im = Image.Image()
        url = 'http://example.com'
        grabber = Grabber(url)

        grabber.get_image_from_url = mocker.Mock(
            grabber.get_image_from_url, autospec=True, return_value=im
        )

        expected_result = {
            'requested_at': fake_datetime,
            'url': url,
            'image': im,
            'error': None,
        }

        result = grabber.download_image()

        grabber.get_image_from_url.assert_called_once_with(url)
        assert result == expected_result
        mocked_datetime.now.assert_called_once_with()

    def test_download_image__exception_raised(self, mocker):
        im = Image.Image()
        url = 'http://example.com'
        grabber = Grabber(url)

        e = Exception()
        grabber.get_image_from_url = mocker.Mock(
            grabber.get_image_from_url,
            autospec=True,
            return_value=im,
            side_effect=e
        )

        grabber.ignore_download_exception = mocker.Mock(
            grabber.ignore_download_exception, autospec=True, side_effect=e
        )

        with pytest.raises(Exception):
            grabber.download_image()

        grabber.get_image_from_url.assert_called_once_with(url)
        grabber.ignore_download_exception.assert_called_once_with(e)

    def test_download_image__exception_ignored(self, mocker):
        mocked_datetime = mocker.patch(
            'camgrab.camgrab.datetime', autospec=True
        )
        fake_datetime = datetime(2017, 1, 2, 12, 13, 14, 987654)
        mocked_datetime.now = mocker.Mock(return_value=fake_datetime)

        im = Image.Image()
        url = 'http://example.com'
        grabber = Grabber(url)

        e = Exception()
        grabber.get_image_from_url = mocker.Mock(
            grabber.get_image_from_url,
            autospec=True,
            return_value=im,
            side_effect=e
        )

        grabber.ignore_download_exception = mocker.Mock(
            grabber.ignore_download_exception,
            autospec=True,
        )

        expected_result = {
            'requested_at': fake_datetime,
            'url': url,
            'image': None,
            'error': e
        }
        result = grabber.download_image()
        assert result == expected_result
        grabber.get_image_from_url.assert_called_once_with(url)
        grabber.ignore_download_exception.assert_called_once_with(e)

    def test_download_image__diff_downloader(self, mocker):
        mocked_datetime = mocker.patch(
            'camgrab.camgrab.datetime', autospec=True
        )
        fake_datetime = datetime(2017, 1, 2, 12, 13, 14, 987654)
        mocked_datetime.now = mocker.Mock(return_value=fake_datetime)

        im = Image.Image()
        url = 'http://example.com'
        grabber = Grabber(url)

        grabber.get_image_from_url = mocker.Mock(
            grabber.get_image_from_url, autospec=True, return_value=im
        )

        expected_result = {
            'requested_at': fake_datetime,
            'url': url,
            'image': im,
            'error': None,
        }

        mock_downloader = mocker.Mock(return_value=im)
        grabber.download_callable = mock_downloader

        result = grabber.download_image()

        grabber.get_image_from_url.assert_not_called()
        mock_downloader.assert_called_once_with(url)
        assert result == expected_result

    def test_ignore_download_exception__ignores_general_exceptions(self):
        grabber = Grabber('http://example.com')
        e = Exception()
        assert grabber.ignore_download_exception(e) is False

    def test_ignore_download_exception(self):
        url = 'http://example.com'
        http_status_codes = (403, 404, 500)

        socket_errors = ((timeout(), 'ignore_timeout'), )

        urllib_errors = []
        for code in http_status_codes:
            urllib_errors.append(
                (
                    HTTPError(url=url, code=code, msg='msg', hdrs={}, fp=None),
                    'ignore_{}'.format(code),
                )
            )

        errors_and_flags = tuple(socket_errors) + tuple(urllib_errors)

        grabber = Grabber('http://example.com')

        for e, flag in errors_and_flags:
            # Ignore error
            setattr(grabber, flag, True)
            assert grabber.ignore_download_exception(e) is True

            # Don't ignore error
            setattr(grabber, flag, False)
            assert grabber.ignore_download_exception(e) is False

    @httpretty.activate
    def test_get_image_from_url(self):
        dummy_url = 'http://a-url.com/'
        dummy_timeout = 123
        dummy_image_path = os.path.join(
            os.path.dirname(__file__), 'assets', 'kitty.jpg'
        )
        dummy_body = open(dummy_image_path, 'rb').read()

        expected_result = Image.open(dummy_image_path)

        httpretty.register_uri(
            httpretty.GET,
            dummy_url,
            body=dummy_body,
            content_type='image/jpeg'
        )

        grabber = Grabber('http://example.com')
        grabber.timeout = dummy_timeout

        result = grabber.get_image_from_url(dummy_url)
        assert result == expected_result

    def test_handle_received_image(self, mocker):
        grabber = Grabber('http://example.com')

        dummy_result = {
            'image': Image.Image(),
            'requested_at': datetime.now(),
            'url': 'http://example.com',
            'error': None
        }

        # If no handlers, then should just return a dict of data
        grabber.get_result_handlers = mocker.Mock(
            'grabber.get_result_handlers', return_value=()
        )
        assert grabber.handle_received_image(dummy_result) == dummy_result
        grabber.get_result_handlers.assert_called_once_with()

        mock_handler_1_return = dummy_result.copy()
        mock_handler_1_return['some_key'] = 'value'
        mock_handler_1 = mocker.Mock(return_value=mock_handler_1_return)

        mock_handler_2_return = dummy_result.copy()
        mock_handler_2_return['another_key'] = 'value'
        mock_handler_2 = mocker.Mock(return_value=mock_handler_2_return)

        grabber.get_result_handlers = mocker.Mock(
            'grabber.get_result_handlers',
            return_value=(mock_handler_1, mock_handler_2),
        )

        result = grabber.handle_received_image(dummy_result)

        assert result == mock_handler_2_return
        mock_handler_1.assert_called_once_with(dummy_result, grabber)
        mock_handler_2.assert_called_once_with(mock_handler_1_return, grabber)

    def test_get_result_handlers(self, mocker):
        grabber = Grabber('http://example.com')

        # When nothing is set, should still return an iterable
        grabber.default_result_handlers = None
        grabber.extra_result_handlers = None
        grabber.result_handlers = None
        assert grabber.get_result_handlers() == ()

        grabber.default_result_handlers = ()
        grabber.extra_result_handlers = ()
        grabber.result_handlers = None
        assert grabber.get_result_handlers() == ()

        grabber.default_result_handlers = ()
        grabber.extra_result_handlers = ()
        grabber.result_handlers = ()
        assert grabber.get_result_handlers() == ()

        mock_handler_1 = mocker.Mock()
        mock_handler_2 = mocker.Mock()
        mock_handler_3 = mocker.Mock()
        mock_handler_4 = mocker.Mock()

        grabber.default_result_handlers = (mock_handler_1, )
        grabber.extra_result_handlers = ()
        grabber.result_handlers = None
        assert grabber.get_result_handlers() == (mock_handler_1, )

        grabber.default_result_handlers = ()
        grabber.extra_result_handlers = (mock_handler_1, )
        grabber.result_handlers = None
        assert grabber.get_result_handlers() == (mock_handler_1, )

        grabber.default_result_handlers = (mock_handler_1, )
        grabber.extra_result_handlers = (mock_handler_1, )
        grabber.result_handlers = None
        assert grabber.get_result_handlers(
        ) == (mock_handler_1, mock_handler_1)

        grabber.default_result_handlers = (mock_handler_1, )
        grabber.extra_result_handlers = (mock_handler_1, )
        grabber.result_handlers = (mock_handler_3, mock_handler_4)
        assert grabber.get_result_handlers(
        ) == (mock_handler_3, mock_handler_4)

        grabber.default_result_handlers = (mock_handler_1, mock_handler_2)
        grabber.extra_result_handlers = (mock_handler_1, mock_handler_3)
        grabber.result_handlers = None
        assert grabber.get_result_handlers(
        ) == (mock_handler_1, mock_handler_2, mock_handler_1, mock_handler_3)

    def test_should_save_image(self):
        good_grabber = Grabber('http://example.com')

        good_grabber.save = True
        good_grabber.save_filename = 'some_filename'
        good_grabber.save_dir = 'some_dir'
        assert good_grabber.should_save_image() is True

        no_save_grabber = Grabber('http://example.com')
        no_save_filename_grabber = Grabber('http://example.com')
        no_save_dir_grabber = Grabber('http://example.com')

        no_save_grabber.save = False
        no_save_grabber.save_filename = 'some_filename'
        no_save_grabber.save_dir = 'some_dir'

        no_save_filename_grabber.save = True
        no_save_filename_grabber.save_filename = None
        no_save_filename_grabber.save_dir = 'some_dir'

        no_save_dir_grabber.save = True
        no_save_dir_grabber.save_filename = 'some_filename'
        no_save_dir_grabber.save_dir = None

        bad_grabbers = (
            no_save_grabber, no_save_dir_grabber, no_save_filename_grabber
        )
        for grabber in bad_grabbers:
            assert grabber.should_save_image() is False

    def test_do_save_image__no_image(self, mocker):
        grabber = Grabber('http://example.com')

        im = Image.Image()
        im.save = mocker.Mock(im.save, autospec=True)

        dummy_result = {
            'image': None,
            'url': 'http://example.com',
            'error': None,
            'requested_at': datetime.now(),
        }

        dummy_save_path = 'some/save/path.jpg'
        grabber.get_full_save_path = mocker.Mock(
            grabber.get_full_save_path,
            autospec=True,
            return_value=dummy_save_path
        )
        grabber.make_save_path_dirs = mocker.Mock(
            grabber.make_save_path_dirs, autospec=True
        )
        grabber.should_save_image = mocker.Mock(
            grabber.should_save_image, autospec=True, return_value=False
        )

        expected_result = dummy_result.copy()
        expected_result['is_saved'] = False
        expected_result['save_dir'] = grabber.save_dir
        expected_result['save_full_path'] = dummy_save_path

        result = grabber.do_save_image(dummy_result, grabber)

        grabber.get_full_save_path.assert_called_once_with()
        grabber.should_save_image.assert_not_called()
        grabber.make_save_path_dirs.assert_not_called()
        im.save.assert_not_called()
        assert result == expected_result

    def test_do_save_image__save_disabled(self, mocker):
        grabber = Grabber('http://example.com')

        im = Image.Image()
        im.save = mocker.Mock(im.save, autospec=True)

        dummy_result = {
            'image': im,
            'url': 'http://example.com',
            'error': None,
            'requested_at': datetime.now(),
        }

        dummy_save_path = 'some/save/path.jpg'
        grabber.get_full_save_path = mocker.Mock(
            grabber.get_full_save_path,
            autospec=True,
            return_value=dummy_save_path
        )

        grabber.make_save_path_dirs = mocker.Mock(
            grabber.make_save_path_dirs, autospec=True
        )

        grabber.should_save_image = mocker.Mock(
            grabber.should_save_image, autospec=True, return_value=False
        )

        expected_result = dummy_result.copy()
        expected_result['is_saved'] = False
        expected_result['save_dir'] = grabber.save_dir
        expected_result['save_full_path'] = dummy_save_path

        result = grabber.do_save_image(dummy_result, grabber)

        grabber.get_full_save_path.assert_called_once_with()
        grabber.should_save_image.assert_called_with()
        grabber.make_save_path_dirs.assert_not_called()
        im.save.assert_not_called()
        assert result == expected_result

    def test_do_save_image__save_enabled(self, mocker):
        grabber = Grabber('http://example.com')

        im = Image.Image()
        im.save = mocker.Mock(im.save, autospec=True)

        dummy_result = {
            'image': im,
            'url': 'http://example.com',
            'error': None,
            'requested_at': datetime.now(),
        }

        dummy_save_path = 'some/save/path.jpg'
        grabber.get_full_save_path = mocker.Mock(
            grabber.get_full_save_path,
            autospec=True,
            return_value=dummy_save_path
        )

        grabber.make_save_path_dirs = mocker.Mock(
            grabber.make_save_path_dirs, autospec=True
        )

        grabber.should_save_image = mocker.Mock(
            grabber.should_save_image, autospec=True, return_value=True
        )

        expected_result = dummy_result.copy()
        expected_result['is_saved'] = True
        expected_result['save_dir'] = grabber.save_dir
        expected_result['save_full_path'] = dummy_save_path

        result = grabber.do_save_image(dummy_result, grabber)

        assert result == expected_result
        grabber.get_full_save_path.assert_called_once_with()
        grabber.make_save_path_dirs.assert_called_once_with(dummy_save_path)
        grabber.should_save_image.assert_called_with()
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
        grabber.save_dir = dummy_save_dir
        grabber.save_filename = '{Y}-{m}-{d}/{Y}{m}{d}-{H}{M}{S}.jpg'
        assert grabber.generate_meta(saved=True) == expected

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
        grabber.save_dir = 'a_dir'
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
