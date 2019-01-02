from setuptools import setup

setup(
    name="habstranslate",
    version="0.0.1",
    packages=["habstranslate"],
    install_requires=["attrs", "bs4", "langdetect", "requests", "praw", "tldextract"],
)
