import json
import re
from pprint import pprint
from io import StringIO

import bs4.element
import langdetect
import praw
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from requests import Request

ua = UserAgent()

_RE_TRIM_WHITESPACE_BLOCKS = re.compile(r"[\t\n\r\s]{2,}")
_RE_TRIM_WHITESPACE = re.compile(r"[\t\n\r\s]")
_RE_SPLIT = re.compile(r"[\t\n\r\s]+")


def quote(url):
    return url.replace("(", "\(").replace(")", "\)")


def process_submission(submission):
    headers = {
        'User-Agent': ua.random,
    }
    resp = requests.get(submission.url, headers=headers)
    resp.raise_for_status()
    doc = BeautifulSoup(resp.text, "html.parser")
    words = []
    for elem in doc.find_all('a'):
        text = elem.text
        for word in _RE_SPLIT.split(text):
            if len(word) > 0 and len(word) <= 25:
                words.append(word)
    all_text = ' '.join(words)
    lang = langdetect.detect(all_text)
    params = None

    if lang == "en":
        params = dict(sl="auto", tl="fr", u=submission.url)
    elif lang == "fr":
        params = dict(sl="auto", tl="en", u=submission.url)

    if params:
        req = Request('GET', "https://translate.google.com/translate", params=params)
        prepped = req.prepare()
        try:
            submission.reply("[Translated]({})".format(quote(prepped.url)))
        except praw.exceptions.APIException as e:
            if e.error_type == 'TOO_OLD':
                pass
            else:
                raise


class Cache():

    def __init__(self):
        try:
            with open('cache.json') as f:
                items = json.load(f)
                self._known_submissions = set(items)
        except (FileNotFoundError, json.JSONDecodeError):
            self._known_submissions = set()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        with open('cache.json', 'w') as f:
            json.dump(list(self._known_submissions), f)

    def has(self, submission):
        return submission.id in self._known_submissions

    def add(self, submission):
        self._known_submissions.add(submission.id)


def main():
    with open('config.json') as f:
        config = json.load(f)

        reddit = praw.Reddit(client_id=config['client_id'],
                             client_secret=config['client_secret'],
                             username=config['username'],
                             password=config['password'],
                             user_agent=config['user_agent'])

        subreddit = reddit.subreddit(config['subreddit'])

        with Cache() as cache:
            for submission in subreddit.stream.submissions():
                if cache.has(submission):
                    continue
                cache.add(submission)
                print(submission.title)
                if not submission.is_self:
                    try:
                        process_submission(submission)
                    except Exception as e:
                        raise


if __name__ == '__main__':
    main()
