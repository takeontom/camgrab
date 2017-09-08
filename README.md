# camgrab

Python based tool to periodically download and save images from network accessible webcams which expose their images via a publically accessible URL to a JPEG image.

## Features

* Handles any webcam which provides a publically accessible URL to a JPG snapshot of their current image.
* Highly configurable.
* Provides a simple base for more advanced functionality, such as motion detection, CCTV systems, image analysis, etc.

## Known supported webcam types

* Most Yawcams

## Installation

```
pip install camgrab
```

## Quick start

To simply grabbing images from a webcam every 2 seconds and start saving them to the default `grabbed_images` directory:

```
from camgrab import Grabber

grabber = Grabber('http://78.100.133.169:8888/out.jpg')
grabber.begin()
```

## Usage

### `Grabber(url, every=2, save_to='grabbed_images', send_to_callable=None)`

#### url

Required.

The publically accessible URL for the webcam image, is likely going to be something like: `'http://78.100.133.169:8888/out.jpg'`.

It is important the URL is to the actual image, not HTML page displaying or linking to the image.

Only webcams which provide images in JPG format are currently supported. It will not work if your webcam only provides a video stream, or displays snapshots in `.flv` format or something else other than an actual image file.

#### every

Optional.

Defaults to `2`.

Defines how many seconds to wait before each attempt at grabbing an image. Floats are fine for the number of seconds, so `0.2` will attempt to grab an image 5 times a second.

If you're grabbing images from a publically available webcam which you don't own, then please respect the owner of the webcam and don't cause a DOS attack by setting the delay too low.

#### save_dir

Optional.

Defaults to `grabbed_images`.

The directory to save grabbed images to.

Can be a directory relative to the current project, or an absolute path to anywhere on your system.

Will attempt to create the directory if it does not exist.

Set to `None` if you do not wish the images to be saved anywhere.

#### send_to_callable

Optional.

Defaults to `None`.

Supply a callable and the Grabber will pass each downloaded image (as a Pillow image) and meta information to the callable.

Example:

```
def print_dimensions(im, **meta):
  width, height = im.size
  print('Image is {width} pixels wide and {height} pixels high!'.format(width, height))

grabber = Grabber('http://78.100.133.169:8888/out.jpg', send_to_callable=print_dimensions)
grabber.begin()
```

The supplied `meta` data is:

* `save_dir`: the directory Grabber is configured to save images into.
* `save_full_path`: the final path which the image might be saved to by the Grabber.
* `is_saved`: whether the Grabber has actually saved the image to the `save_full_path`.
* `url`: the source URL for the image.
* `timestamp`: a Python datetime giving the date and time the image was grabbed.

Passing the grabbed images to a callable provides an easy way to hook in extra functionality. For example, it allows you to easily use motion detectors, image manipulators and analysers.
