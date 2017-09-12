#!/usr/bin/env python

from distutils.core import setup

setup(
    name='camgrab',
    version='0.8',
    description='Python library for grabbing images from webcams',
    author='Tom Smith',
    author_email='tom@takeontom.com',
    url='https://github.com/takeontom/camgrab',
    packages=['camgrab'],
    install_requires=('pillow>=4'),
    license="MIT license",
    classifiers=(
            'Development Status :: 2 - Pre-Alpha',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: MIT License',
            'Natural Language :: English',
            'Programming Language :: Python :: 3.5',
            'Programming Language :: Python :: 3.6',
    ),
)
