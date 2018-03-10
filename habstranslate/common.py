import json
import re
from threading import Event, RLock, Thread
from urllib.parse import urlparse

import requests
from requests import Request

import langdetect
import praw
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

from datetime import datetime, timedelta

_RE_SPLIT = re.compile(r"[\t\n\r\s]+")


ua = UserAgent()


class Task:

    def __init__(self, config, whitelist):
        self._conf = config
        self._whitelist = whitelist
        self._stop = Event()
        self._thread = Thread(target=self.run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    def join(self):
        self._thread.join()

    def should_stop(self):
        return self._stop.is_set()

    def save_state(self):
        raise NotImplementedError

    def run(self):
        raise NotImplementedError

    def process_submission(self, submission):
        try:
            # from pprint import pprint
            # pprint(vars(submission))
            printf("Analyzing submission {}", submission.title)

            if submission.is_self:
                printf("Self post submission, skipping")
                return

            created = datetime.utcfromtimestamp(submission.created_utc)
            if (datetime.utcnow() - created) > timedelta(days=1):
                printf("Submission is older than a day, skipping")
                return

            if submission.url not in self._whitelist:
                printf("Website is not whitelisted, skipping")
                return

            if any(comment.author.name.lower() == self._conf['username'].lower()
                   for comment in submission.comments if comment.is_root):
                printf("Submission has already been replied to, skipping")
                return

            headers = {
                'User-Agent': ua.random,
            }
            resp = requests.get(submission.url, headers=headers)
            resp.raise_for_status()
            if "text/html" not in resp.headers['content-type']:
                return

            doc = BeautifulSoup(resp.text, "html.parser")
            lang = detect_lang(doc)

            message = None

            if lang == "en":
                translation_url = translate_url(submission.url, "fr")
                message = "[Traduction]({})".format(translation_url)
            elif lang == "fr":
                translation_url = translate_url(submission.url, "en")
                message = "[Translation]({})".format(translation_url)
            if message:
                try:
                    printf("Replying with translated link")
                    submission.reply(message)
                except praw.exceptions.APIException as e:
                    if e.error_type == 'TOO_OLD':
                        pass
                    else:
                        raise
        finally:
            printf("------")


def quote(url):
    return url.replace("(", "\(").replace(")", "\)")


def printf(fmt, *args, **kwargs):
    print(fmt.format(*args, **kwargs))


def detect_lang(doc):
    words = []
    for elem in doc.find_all('p'):
        text = elem.text
        for word in _RE_SPLIT.split(text):
            if len(word) > 0 and len(word) <= 25:
                words.append(word)
    all_text = ' '.join(words)
    return langdetect.detect(all_text)


def reddit_from_conf(config):
    return praw.Reddit(client_id=config['client_id'],
                       client_secret=config['client_secret'],
                       username=config['username'],
                       password=config['password'],
                       user_agent=config['user_agent'])


def translate_url(url, target):
    params = dict(sl="auto", tl=target, u=url)
    req = Request('GET', "https://translate.google.com/translate", params=params)
    prepped = req.prepare()
    return quote(prepped.url)


def get_domain(url):
    url = urlparse(url)
    return url.netloc.lower()


class Whitelist:

    def __init__(self, path="whitelist.json"):
        self._lock = RLock()
        self._path = path
        try:
            with open(path) as f:
                self._domains = set(json.load(f))
        except FileNotFoundError:
            self._domains = set()

    def save(self):
        with self._lock:
            with open(self._path, 'w') as f:
                json.dump(list(self._domains), f)

    def add(self, url_or_domain):
        with self._lock:
            self._domains.add(get_domain(url_or_domain))

    def __contains__(self, url_or_domain):
        with self._lock:
            return get_domain(url_or_domain) in self._domains
