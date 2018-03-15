from setuptools import setup

setup(
    name="habstranslate",
    version="0.0.1",
    packages=['habstranslate'],
    install_requires=['attrs', 'bs4', 'fake_useragent', 'langdetect', 'requests', 'praw', 'tldextract']
)
