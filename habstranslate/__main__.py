import json
import re

import langdetect
import praw
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from requests import Request

from .cache import LRUContext

ua = UserAgent()

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


def main():
    with open('config.json') as f:
        config = json.load(f)

        reddit = praw.Reddit(client_id=config['client_id'],
                             client_secret=config['client_secret'],
                             username=config['username'],
                             password=config['password'],
                             user_agent=config['user_agent'])

        subreddit = reddit.subreddit(config['subreddit'])

        with LRUContext("lru_cache.txt", 150) as cache:
            try:
                for submission in subreddit.stream.submissions():
                    if cache.has(submission.id):
                        continue
                    cache.add(submission.id)
                    print(submission.title)
                    if not submission.is_self:
                        try:
                            process_submission(submission)
                        except Exception as e:
                            raise
            except KeyboardInterrupt:
                print()
                pass


if __name__ == '__main__':
    main()
