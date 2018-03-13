import json
import sys
from datetime import datetime, timedelta
from threading import Event, RLock, Thread

import requests
from requests import Request

import praw
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from tldextract import TLDExtract

from .detection import detect_lang

ua = UserAgent()
tldextract = TLDExtract(suffix_list_urls=None)


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
            lang = detect_lang(doc, get_domain(submission.url))

            message = None

            if lang == "en":
                message = "[Traduction]({})\n\n[Lien alternatif]({})".format(
                    google_translate_url(submission.url, "fr"),
                    bing_translate_url(submission.url, "fr")
                )
            elif lang == "fr":
                message = "[Translation]({})\n\n[Alternate link]({})".format(
                    google_translate_url(submission.url, "fr"),
                    bing_translate_url(submission.url, "fr")
                )
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
    sys.stdout.write(fmt.format(*args, **kwargs))
    sys.stdout.write("\n")
    sys.stdout.flush()


def reddit_from_conf(config):
    return praw.Reddit(client_id=config['client_id'],
                       client_secret=config['client_secret'],
                       username=config['username'],
                       password=config['password'],
                       user_agent=config['user_agent'])


def url_with_params(base_url, params=None):
    req = Request('GET', base_url, params=params)
    prepped = req.prepare()
    return prepped.url


def google_translate_url(url, target):
    params = dict(sl="auto", tl=target, u=url)
    return quote(url_with_params("https://translate.google.com/translate", params))


def bing_translate_url(url, target):
    params = {'from': '', 'to': target, 'a': url}
    return quote(url_with_params("http://www.microsofttranslator.com/bv.aspx", params))


def get_domain(url):
    info = tldextract(url)
    domain = '.'.join(part for part in [info.domain, info.suffix] if part)
    return domain.lower()


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
