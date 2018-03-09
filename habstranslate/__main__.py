import json
import re
from urllib.parse import urlparse
from pprint import pprint

import langdetect
import praw
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from requests import Request

ua = UserAgent()

_RE_SPLIT = re.compile(r"[\t\n\r\s]+")
_BLACKLIST = [
    "youtube.com",
    "youtu.be",
    "streamable.com",
    "imgur.com",
]


def is_blacklisted(url):
    url = urlparse(url)
    domain = url.netloc.lower()
    return any(site in domain for site in _BLACKLIST)


def printf(fmt, *args, **kwargs):
    print(fmt.format(*args, **kwargs))


def quote(url):
    return url.replace("(", "\(").replace(")", "\)")


def process_submission(submission):
    if is_blacklisted(submission.url):
        return

    headers = {
        'User-Agent': ua.random,
    }
    resp = requests.get(submission.url, headers=headers)
    resp.raise_for_status()
    pprint(resp.headers)
    if "text/html" not in resp.headers['content-type']:
        return

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

        username = config['username']

        reddit = praw.Reddit(client_id=config['client_id'],
                             client_secret=config['client_secret'],
                             username=username,
                             password=config['password'],
                             user_agent=config['user_agent'])

        subreddit = reddit.subreddit(config['subreddit'])

        for submission in subreddit.stream.submissions():
            if not submission.is_self:  # link submission
                # make sure we haven't replied already
                process = True
                for comment in submission.comments:
                    if comment.is_root and comment.author.name.lower() == username.lower():
                        process = False
                        break
                if process:
                    printf("Processing '{}', repliying with translated link", submission.title)
                    try:
                        process_submission(submission)
                    except Exception as e:
                        raise
                else:
                    printf("Processing '{}', skipping because it has already been replied to", submission.title)


if __name__ == '__main__':
    main()
