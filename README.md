# camgrab

Python library to download images from network accessible webcams.

## Features

* Out of the box, handles any webcam which provides a publically accessible URL to a JPG snapshot of their current image.
* Easily swap in different downloaders to handle cams which expose their snapshots in a more complex way.
* Highly configurable.
* Provides a simple base for more advanced functionality, such as motion detection, CCTV systems, image analysis, etc.

## Installation

```shell
pip install camgrab
```

## Quick start

To simply grabbing images from a webcam every 2 seconds and start saving them to the default `grabbed_images` directory:

```python
from camgrab import Grabber

grabber = Grabber('http://78.100.133.169:8888/out.jpg')
grabber.begin()
```

## Examples
