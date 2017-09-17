import os
from datetime import datetime
from socket import timeout
from urllib.error import HTTPError, URLError

import httpretty
import pytest
from PIL import Image

from camgrab.camgrab import Grabber, do_save_image, get_image_from_url


class TestGrabber_IntegrationTests(object):
    @httpretty.activate
    def test_save_simple_image(self, mocker):
        dummy_datetime = datetime(2017, 1, 2, 12, 13, 14, 987654)
        mocked_datetime = mocker.patch(
            'camgrab.camgrab.datetime',
            autospec=True,
            return_value=dummy_datetime
        )
        mocked_datetime.now = mocker.Mock(return_value=dummy_datetime)
        mock_sleep = mocker.patch('camgrab.camgrab.sleep', autospec=True)
        mock_image_save = mocker.patch('camgrab.camgrab.Image.Image.save')
        mock_makedirs = mocker.patch('camgrab.camgrab.makedirs')

        dummy_url = 'http://some-url.com/image.jpg'
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

        num_ticks = 5
        every = 5
        save_dir = 'some_dir'

        grabber = Grabber(dummy_url, every=every, save_dir=save_dir)
        grabber._test_max_ticks = num_ticks

        grabber.save_filename = '{Y}{m}{d}/{H}/{Y}{m}{d}-{H}{M}{S}-{f}.jpg'

        expected_dir = 'some_dir/20170102/12'
        expected_filename = 'some_dir/20170102/12/20170102-121314-987654.jpg'

        grabber.begin()

        assert mock_sleep.call_count == num_ticks
        mock_sleep.assert_called_with(every)

        assert mock_image_save.call_count == num_ticks
        mock_image_save.assert_called_with(expected_filename)

        assert mock_makedirs.call_count == num_ticks
        mock_makedirs.assert_called_with(expected_dir, exist_ok=True)


class TestGrabber(object):
    def test_init(self):
        url = 'http://example.com'
        grabber = Grabber(url)

        # Default attribute values
        assert grabber.url == url
        assert grabber.every == 2
        assert grabber.save_dir == 'grabbed_images'
        assert grabber.download_callable == get_image_from_url
        assert grabber.default_result_handlers == (do_save_image, )
        assert grabber.extra_result_handlers == []
        assert grabber.result_handlers is None
        assert grabber.timeout == 30
        assert grabber.save_filename == (
            '{Y}{m}{d}/{H}/{Y}{m}{d}-{H}{M}{S}-{f}.jpg'
        )
        assert grabber.save is True

        assert grabber.ignore_timeout is True

        ignore_status_codes = (
            307, 400, 408, 409, 429, 444, 451, 499, 500, 502, 503, 504, 507,
            599
        )
        for code in ignore_status_codes:
            assert getattr(grabber, 'ignore_{}'.format(code)) is True

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
        mock_sleep = mocker.patch('camgrab.camgrab.sleep', autospec=True)

        grabber.begin()

        assert grabber.tick.call_count == 5
        assert mock_sleep.call_count == 5
        mock_sleep.assert_called_with(13)

    def test_tick(self, mocker):
        im = Image.Image()

        dummy_request = {
            'url': 'http://example.com',
            'requested_at': datetime.now()
        }

        grabber = Grabber('http://example.com')
        grabber.create_request = mocker.Mock(
            grabber.create_request, autospec=True, return_value=dummy_request
        )

        dummy_result = {'image': im, 'requested_at': datetime.now()}

        grabber.download_image = mocker.Mock(
            grabber.download_image, autospec=True, return_value=dummy_result
        )
        grabber.handle_received_image = mocker.Mock(
            grabber.handle_received_image, autospec=True
        )

        grabber.tick()

        grabber.create_request.assert_called_once_with()
        grabber.download_image.assert_called_once_with(dummy_request)
        grabber.handle_received_image.assert_called_once_with(dummy_result)

    def test_create_request(self, mocker):
        mocked_datetime = mocker.patch(
            'camgrab.camgrab.datetime', autospec=True
        )
        dummy_datetime = datetime(2017, 1, 2, 12, 13, 14, 987654)
        mocked_datetime.now = mocker.Mock(return_value=dummy_datetime)

        url = 'http://example.com'
        grabber = Grabber(url)

        expected_request = {
            'url': url,
            'requested_at': dummy_datetime,
        }

        assert grabber.create_request() == expected_request
        mocked_datetime.now.assert_called_once_with()

    def test_download_image(self, mocker):
        correct_url = 'http://example.com'
        dummy_image = Image.Image()
        now = datetime.now()

        dummy_request = {'requested_at': now, 'url': correct_url}
        dummy_downloader = mocker.Mock(return_value=dummy_image)

        grabber = Grabber('http://bad-url.com', save_dir='some/dir')
        grabber.get_download_callable = mocker.Mock(
            grabber.get_download_callable,
            autospec=True,
            return_value=dummy_downloader
        )

        expected_result = {
            'requested_at': now,
            'url': correct_url,
            'image': dummy_image,
            'error': None,
        }

        result = grabber.download_image(dummy_request)

        assert result == expected_result
        dummy_downloader.assert_called_once_with(correct_url, grabber)
        grabber.get_download_callable.assert_called_once_with()

    def test_download_image__exception_raised(self, mocker):
        correct_url = 'http://example.com'
        now = datetime.now()
        e = Exception()

        dummy_request = {'requested_at': now, 'url': correct_url}
        dummy_downloader = mocker.Mock(side_effect=e)

        grabber = Grabber('http://bad-url.com')
        grabber.get_download_callable = mocker.Mock(
            grabber.get_download_callable,
            autospec=True,
            return_value=dummy_downloader,
        )
        grabber.ignore_download_exception = mocker.Mock(
            grabber.ignore_download_exception,
            autospec=True,
            return_value=False
        )

        with pytest.raises(Exception):
            grabber.download_image(dummy_request)

        grabber.get_download_callable.assert_called_once_with()
        dummy_downloader.assert_called_once_with(correct_url, grabber)
        grabber.ignore_download_exception.assert_called_once_with(e)

    def test_download_image__exception_ignored(self, mocker):
        correct_url = 'http://example.com'
        now = datetime.now()
        e = Exception()

        dummy_request = {'requested_at': now, 'url': correct_url}
        dummy_downloader = mocker.Mock(side_effect=e)

        grabber = Grabber('http://bad-url.com')
        grabber.get_download_callable = mocker.Mock(
            grabber.get_download_callable,
            autospec=True,
            return_value=dummy_downloader,
        )
        grabber.ignore_download_exception = mocker.Mock(
            grabber.ignore_download_exception,
            autospec=True,
            return_value=True
        )

        expected_result = {
            'requested_at': now,
            'url': correct_url,
            'image': None,
            'error': e
        }

        result = grabber.download_image(dummy_request)

        assert result == expected_result
        grabber.get_download_callable.assert_called_once_with()
        dummy_downloader.assert_called_once_with(correct_url, grabber)
        grabber.ignore_download_exception.assert_called_once_with(e)

    def test_get_download_callable(self, mocker):
        grabber = Grabber('http://example.com')

        mock_downloader = mocker.Mock()
        grabber.download_callable = mock_downloader

        assert grabber.get_download_callable() is mock_downloader

    def test_ignore_download_exception__ignores_general_exceptions(self):
        grabber = Grabber('http://example.com')
        e = Exception()
        assert grabber.ignore_download_exception(e) is False

    def test_ignore_download_exception(self):
        url = 'http://example.com'

        socket_errors = ((timeout(), 'ignore_timeout'), )

        urllib_errors = (
            (URLError(reason=timeout(), filename=None), 'ignore_timeout'),
        )

        http_status_codes = (403, 404, 500)
        http_errors = []
        for code in http_status_codes:
            http_errors.append(
                (
                    HTTPError(url=url, code=code, msg='msg', hdrs={}, fp=None),
                    'ignore_{}'.format(code),
                )
            )

        errors_and_flags = (
            tuple(socket_errors) + tuple(urllib_errors) + tuple(http_errors)
        )

        grabber = Grabber('http://example.com')

        for e, flag in errors_and_flags:
            # Ignore error
            setattr(grabber, flag, True)
            assert grabber.ignore_download_exception(e) is True

            # Don't ignore error
            setattr(grabber, flag, False)
            assert grabber.ignore_download_exception(e) is False

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

    def test_handle_received_image__no_result_return(self, mocker):
        dummy_result_original = {
            'image': Image.Image(),
            'requested_at': datetime.now(),
            'url': 'http://example.com',
            'error': None
        }

        dummy_result_after_1 = dummy_result_original.copy()
        dummy_result_after_1['handler_1'] = 'done'

        dummy_result_after_3 = dummy_result_after_1.copy()
        dummy_result_after_3['handler_3'] = 'done'

        mock_handler_1 = mocker.Mock(return_value=dummy_result_after_1)
        mock_handler_2 = mocker.Mock(return_value=None)
        mock_handler_3 = mocker.Mock(return_value=dummy_result_after_3)

        grabber = Grabber('http://example.com')

        mocker.patch.object(
            grabber,
            'get_result_handlers',
            return_value=(mock_handler_1, mock_handler_2, mock_handler_3)
        )

        result = grabber.handle_received_image(dummy_result_original)

        grabber.get_result_handlers.assert_called_once_with()

        mock_handler_1.assert_called_once_with(dummy_result_original, grabber)
        mock_handler_2.assert_called_once_with(dummy_result_after_1, grabber)
        mock_handler_3.assert_called_once_with(dummy_result_after_1, grabber)

        assert result == dummy_result_after_3

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

    def test_create_save_path_dirs(self, mocker):
        mocked_makedirs = mocker.patch('camgrab.camgrab.makedirs')
        path = 'a_dir/somewhere/another_dir/final_file.jpg'

        grabber = Grabber('http://example.com')

        grabber.make_save_path_dirs(path)

        mocked_makedirs.assert_called_once_with(
            'a_dir/somewhere/another_dir', exist_ok=True
        )

    def test_get_save_path(self, mocker):
        mocked_datetime = mocker.patch(
            'camgrab.camgrab.datetime', autospec=True
        )
        fake_datetime = datetime(2017, 1, 2, 12, 13, 14, 987654)
        mocked_datetime.now = mocker.Mock(return_value=fake_datetime)

        grabber = Grabber('http://example.com')
        grabber.save_dir = 'a_dir'
        grabber.save_filename = '{Y}{m}{d}/blah/{H}{M}{S}{f}.jpg'

        expected = 'a_dir/{Y}{m}{d}/blah/{H}{M}{S}{f}.jpg'

        grabber.format_path = mocker.Mock(
            grabber.format_path, autospec=True, return_value=expected
        )

        full_save_path = grabber.get_save_path()
        assert full_save_path == expected

    def test_format_path(self, mocker):
        request = {
            'requested_at': datetime(2017, 1, 2, 12, 13, 14, 987654),
            'url': 'http://a-url.co.uk:1234/some_path/0123456789/some-file.jpg'
        }

        path_format = 'a_dir/{url}/{Y}{m}{d}/{H}{M}{S}-{f}.jpg'

        expected = (
            'a_dir/'
            'http-a-url-co-uk-1234-some_path-0123456789-some-file-jpg/'
            '20170102/121314-987654.jpg'
        )

        grabber = Grabber('http://example.com')
        result = grabber.format_path(path_format, request)
        assert result == expected

    def test_slugify(self):
        grabber = Grabber('http://example.com')

        tests = (
            ('abcDEFghi', 'abcdefghi'),
            ('a-a b_b c.c d:d', 'a-a-b_b-c-c-d-d'),
        )

        for value, expected in tests:
            assert grabber.slugify(value) == expected


class Test_get_image_from_url():
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

        result = get_image_from_url(dummy_url, grabber)
        assert result == expected_result


class Test_do_save_image(object):
    def test_do_save_image__no_image(self, mocker):
        grabber = Grabber('http://example.com')

        dummy_save_path = 'some/{Y}/path.jpg'
        dummy_save_path_full = 'some/2017/path.jpg'

        mocker.patch.object(
            grabber, 'get_save_path', return_value=dummy_save_path
        )
        mocker.patch.object(grabber, 'make_save_path_dirs')
        mocker.patch.object(grabber, 'should_save_image', return_value=True)
        mocker.patch.object(
            grabber, 'format_path', return_value=dummy_save_path_full
        )

        dummy_result = {
            'image': None,
            'url': 'http://example.com',
            'error': None,
            'requested_at': datetime.now(),
        }

        expected_result = dummy_result.copy()
        expected_result['is_saved'] = False
        expected_result['save_dir'] = grabber.save_dir
        expected_result['save_path'] = dummy_save_path
        expected_result['save_path_full'] = dummy_save_path_full

        result = do_save_image(dummy_result, grabber)

        grabber.get_save_path.assert_called_once_with()
        grabber.should_save_image.assert_not_called()
        grabber.make_save_path_dirs.assert_not_called()
        grabber.format_path.assert_called_once_with(dummy_save_path, result)
        assert result == expected_result

    def test_do_save_image__save_disabled(self, mocker):
        grabber = Grabber('http://example.com')

        im = Image.Image()
        mocker.patch.object(im, 'save')

        dummy_save_path = 'some/{Y}/path.jpg'
        dummy_save_path_full = 'some/2017/path.jpg'

        mocker.patch.object(
            grabber, 'get_save_path', return_value=dummy_save_path
        )
        mocker.patch.object(grabber, 'make_save_path_dirs')
        mocker.patch.object(grabber, 'should_save_image', return_value=False)
        mocker.patch.object(
            grabber, 'format_path', return_value=dummy_save_path_full
        )

        dummy_result = {
            'image': im,
            'url': 'http://example.com',
            'error': None,
            'requested_at': datetime.now()
        }

        expected_result = dummy_result.copy()
        expected_result['is_saved'] = False
        expected_result['save_dir'] = grabber.save_dir
        expected_result['save_path'] = dummy_save_path
        expected_result['save_path_full'] = dummy_save_path_full

        result = do_save_image(dummy_result, grabber)

        grabber.get_save_path.assert_called_once_with()
        grabber.should_save_image.assert_called_once_with()
        grabber.make_save_path_dirs.assert_not_called()
        grabber.format_path.assert_called_once_with(dummy_save_path, result)
        im.save.assert_not_called()
        assert result == expected_result

    def test_do_save_image__save_enabled(self, mocker):
        grabber = Grabber('http://example.com')

        im = Image.Image()
        mocker.patch.object(im, 'save')

        dummy_save_path = 'some/{Y}/path.jpg'
        dummy_save_path_full = 'some/2017/path.jpg'

        mocker.patch.object(
            grabber, 'get_save_path', return_value=dummy_save_path
        )
        mocker.patch.object(grabber, 'make_save_path_dirs')
        mocker.patch.object(grabber, 'should_save_image', return_value=True)
        mocker.patch.object(
            grabber, 'format_path', return_value=dummy_save_path_full
        )

        dummy_result = {
            'image': im,
            'url': 'http://example.com',
            'error': None,
            'requested_at': datetime.now(),
        }

        expected_result = dummy_result.copy()
        expected_result['is_saved'] = True
        expected_result['save_dir'] = grabber.save_dir
        expected_result['save_path'] = dummy_save_path
        expected_result['save_path_full'] = dummy_save_path_full

        result = do_save_image(dummy_result, grabber)

        assert result == expected_result
        grabber.format_path.assert_called_once_with(dummy_save_path, result)
        grabber.get_save_path.assert_called_once_with()
        grabber.make_save_path_dirs.assert_called_once_with(
            dummy_save_path_full
        )
        grabber.should_save_image.assert_called_with()
        im.save.assert_called_once_with(dummy_save_path_full)
