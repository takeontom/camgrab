from camgrab.camgrab import Grabber
from datetime import datetime


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

    def test_create_save_path_dirs(self, mocker):
        mocked_makedirs = mocker.patch('camgrab.camgrab.makedirs')
        path = 'a_dir/somewhere/another_dir/final_file.jpg'

        grabber = Grabber('http://example.com')

        grabber.make_save_path_dirs(path)

        mocked_makedirs.assert_called_once_with(
            'a_dir/somewhere/another_dir', exists_ok=True
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
