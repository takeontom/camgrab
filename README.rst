camgrab
=======

Python library to download images from network accessible webcams.

Features
--------

* Out of the box, handles any webcam which provides a publically accessible URL to a JPG snapshot of their current image.
* Easily swap in different downloaders to handle cams which expose their snapshots in a more complex way.
* Highly configurable.
* Provides a simple base for more advanced functionality, such as motion detection, CCTV systems, image analysis, etc.

Installation
------------

.. code:: sh

    pip install camgrab


Quick start
-----------

To simply grabbing images from a webcam every 2 seconds and start saving them to the default `grabbed_images` directory:

.. code:: python

    from camgrab import Grabber
    grabber = Grabber('http://78.100.133.169:8888/out.jpg')
    grabber.begin()

Examples
--------

Adding a custom image handler
.............................

Grab an image every 5 seconds and it to a custom callable, without saving it, and print the image's dimensions.

.. code:: python

    from camgrab import Grabber

    url = 'http://62.163.242.211:8080/out.jpg'


    def print_dimensions(im, **meta):
        width, height = im.size
        print('{width} pixels wide, {height} pixels high!'.format(width=width, height=height))

    grabber = Grabber(url, every=5, send_to_callable=print_dimensions)
    grabber.save = False
    grabber.begin()

Take control of the main loop
.............................

As the main loop created by the `begin()` method is unthreaded, provides no output, has a static delay between grab attempts, etc. it might be too simple for your needs.

To get around this, simply call the `tick()` method within your own loop:

.. code:: python

    from random import random
    from time import sleep

    from camgrab import Grabber

    url = 'http://62.163.242.211:8080/out.jpg'
    grabber = Grabber(url)

    while True:
        grabber.tick()

        # Wait somewhere between 0 and 10 seconds
        sleep(random() * 10)

License
-------

camgrab is free software, distributed under the MIT license.
