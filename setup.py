from os import path

from setuptools import setup

from gearpy import __version__

here = path.abspath(path.dirname(__file__))

setup(
    name='gearpy',
    version=__version__,
    description='tiny web crawler framework',
    url='https://github.com/Kilerd/gear',

    author='Kilerd Chan',
    author_mail='blove694@gmail.com',

    license='MIT',

    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Environment :: Web Environment',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.6',
    ],

    keywords='web async crawler spider',

    packages=['gearpy'],

    install_requires=[
        'aiohttp',
        'beautifulsoup4',
        'lxml'
    ],
    python_requires='>=3.6',
)