camgrab
=======

Python library to download images from network accessible webcams.

Features
--------

* Out of the box, handles any webcam which provides a publically accessible URL
  to a JPG snapshot of their current image.
* Easily swap in different downloaders to handle cams which expose their
  snapshots in a more complex way.
* Highly configurable.
* Provides a simple base for more advanced functionality, such as motion
  detection, CCTV systems, image analysis, etc.

Installation
------------

.. code:: sh

    pip install camgrab


Quick start
-----------

To simply grabbing images from a webcam every 2 seconds and start saving them
to the default `grabbed_images` directory:

.. code:: python

    from camgrab import Grabber

    grabber = Grabber('http://www.masconcable.ca/webcams/chase.jpg')
    grabber.begin()

Examples
--------

Quickly add a custom result handler
...................................

Here we create a custom result handler which will simply print the
dimensions of the grabbed image.

The default result handlers (e.g. `do_save_image()`) will still be used.

.. code:: python

    from camgrab import Grabber

    url = 'http://www.masconcable.ca/webcams/chase.jpg'


    def print_dimensions(result, grabber):
        if not result.get('image', None):
            return

        width, height = result['image'].size
        print(
            '{width} pixels wide, {height} pixels high!'.
            format(width=width, height=height)
        )


    grabber = Grabber(url, every=5, extra_result_handlers=(print_dimensions, ))
    grabber.begin()

More complex result handling
............................

In this example, we'll take full control of the result handling, creating a
chain of result handlers to:

* resize the image to 320x200
* rotate the image by 90 degrees
* save the image
* print the final result dictionary to the terminal

.. code:: python

    from camgrab import Grabber
    from camgrab.camgrab import do_save_image

    url = 'http://www.masconcable.ca/webcams/chase.jpg'


    def resize_image(result, grabber):
        if not result.get('image', None):
            return

        result['image'] = result['image'].resize((320, 200))


    def rotate_image(result, grabber):
        if not result.get('image', None):
            return

        result['image'] = result['image'].rotate(90)


    def print_result(result, grabber):
        print(result)


    # Setting result_handlers attribute completely overrides any default result
    # handlers previously set. Hence making sure `do_save_image` (which is normally
    # a default handler) is in this tuple:
    result_handlers = (resize_image, rotate_image, do_save_image, print_result)

    grabber = Grabber(url, every=5)
    grabber.result_handlers = result_handlers
    grabber.begin()

Take control of the main loop
.............................

If the the main loop created by the `begin()` method is too simple for your
needs, then either override the `begin()` method or simply call `tick()` from
your own consumer.

In this example, we consume a Grabber but define our own (not terribly useful)
main loop which waits a random amount of time between ticks:

.. code:: python

    from random import random
    from time import sleep

    from camgrab import Grabber

    url = 'http://www.masconcable.ca/webcams/chase.jpg'
    grabber = Grabber(url)

    while True:
        grabber.tick()

        # Wait somewhere between 0 and 10 seconds
        sleep(random() * 10)

Error handling
--------------

Grabbing images from webcams is a messy business... They go offline loads, send
corrupted images, sometimes they randomly start sending Server 500 errors, etc.

Because of all this, camgrab's default settings make it pretty tolerant of
common errors which occur when grabbing an image. But this can be configured
easily enough.

HTTP errors
...........

HTTP errors can be ignored or raised by setting `ignore_xxx` attributes. For
example...

By default HTTP 404 errors are not ignored by default. So when a 404 error
occurs the grabber will crash and you can handle the exception in whatever way
you want.

.. code:: python

    from urllib.error import HTTPError

    from camgrab import Grabber

    grabber = Grabber('http://www.masconcable.ca/webcams/chase.jpg')

    try:
        grabber.begin()
    except HTTPError as e:
        if e.code == 404:
            print('Was it something I said?')

If you'd rather HTTP 404 errors didn't cause a crash, then set the `ignore_404`
attribute:

.. code:: python

    from camgrab import Grabber

    grabber = Grabber('http://www.masconcable.ca/webcams/chase.jpg')
    grabber.ignore_404 = True

    grabber.begin()

Now when a 404 error occurs, the Grabber will:

* add the exception to the result dictionary
* set the image in the result dictionary to `None`

And then continue its normal routine.

By default, the following HTTP status codes are ignored:

* 307, 400, 408, 409, 429, 444, 451, 499, 500, 502, 503, 504, 507, 599

Network errors
..............

camgrab ignores network errors by default. If you'd rather network timeouts
caused a crash, then just set the `ignore_timeout` attribute:

.. code:: python

    from socket import timeout
    from urllib.error import URLError

    from camgrab import Grabber

    grabber = Grabber('http://www.masconcable.ca/webcams/chase.jpg')
    grabber.ignore_timeout = False

    try:
        grabber.begin()
    except URLError as e:
        if isinstance(e.reason, timeout):
            print("It's me, not you")

License
-------

camgrab is free software, distributed under the MIT license.
