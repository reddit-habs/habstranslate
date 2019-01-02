import json
import pickle
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

import attr
import requests
from attr import attrib, attrs
from bs4 import BeautifulSoup
from requests import Request

import praw
from tldextract import TLDExtract

from .detection import detect_lang

ua = "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:64.0) Gecko/20100101 Firefox/64.0"
tldextract = TLDExtract(suffix_list_urls=None)


def printf(fmt, *args, **kwargs):
    sys.stdout.write(fmt.format(*args, **kwargs))
    sys.stdout.write("\n")
    sys.stdout.flush()


_in_block = False


@contextmanager
def print_block():
    global _in_block
    if _in_block:
        yield
    else:
        _in_block = True
        yield
        printf("-------")
        _in_block = False


def quote(url):
    return url.replace("(", r"\(").replace(")", r"\)")


def reddit_from_conf(config):
    return praw.Reddit(
        client_id=config.client_id,
        client_secret=config.client_secret,
        username=config.username,
        password=config.password,
        user_agent=config.user_agent,
    )


def url_with_params(base_url, params=None):
    req = Request("GET", base_url, params=params)
    prepped = req.prepare()
    return prepped.url


def google_translate_url(url, source, target):
    params = dict(sl=source, tl=target, u=url)
    return quote(url_with_params("https://translate.google.com/translate", params))


def bing_translate_url(url, source, target):
    params = {"from": source, "to": target, "a": url}
    return quote(url_with_params("http://www.microsofttranslator.com/bv.aspx", params))


def get_domain(url):
    info = tldextract(url)
    domain = ".".join(part for part in [info.domain, info.suffix] if part)
    return domain.lower()


def process_submission(config, storage, submission, replies):
    with print_block():
        printf("Analyzing submission {}", submission.title)

        if submission.is_self:
            printf("Self post submission, skipping")
            return

        created = datetime.utcfromtimestamp(submission.created_utc)
        if (datetime.utcnow() - created) > timedelta(days=1):
            printf("Submission is older than a day, skipping")
            return

        if not storage.is_whitelisted(submission.url):
            printf("Website is not whitelisted, skipping")
            return

        if submission in replies:
            printf("Submission is in the replies set, skipping")
            return

        if any(
            comment.author.name.lower() == config.username.lower() for comment in submission.comments if comment.is_root
        ):
            printf("Submission has already been replied to, skipping")
            return

        headers = {"User-Agent": ua}
        resp = requests.get(submission.url, headers=headers)
        resp.raise_for_status()
        if "text/html" not in resp.headers["content-type"]:
            return

        doc = BeautifulSoup(resp.text, "html.parser")
        lang = detect_lang(doc, get_domain(submission.url))

        message = None

        if lang == "en":
            message = "[Traduction]({})\n\n[Lien alternatif]({})".format(
                google_translate_url(submission.url, "en", "fr"), bing_translate_url(submission.url, "en", "fr")
            )
        elif lang == "fr":
            message = "[Translation]({})\n\n[Alternate link]({})".format(
                google_translate_url(submission.url, "fr", "en"), bing_translate_url(submission.url, "fr", "en")
            )
        if message:
            try:
                printf("Replying with translated link")
                submission.reply(message)
                replies.add(submission)
            except praw.exceptions.APIException as e:
                if e.error_type == "TOO_OLD":
                    pass
                else:
                    raise


def from_dict(cons, json):
    return cons(**json)


def from_json(cons, path):
    with open(path) as f:
        return from_dict(cons, json.load(f))


@attrs(slots=True)
class Config:
    client_id = attrib()
    client_secret = attrib()
    username = attrib()
    password = attrib()
    user_agent = attrib(default="habstranslate")
    subreddit = attrib(default="habs")
    authorized_users = attrib(default=attr.Factory(list))


@attrs(slots=True)
class Storage:
    before = attrib(default=0)
    _domains = attrib(default=attr.Factory(set))

    def whitelist(self, url_or_domain):
        self._domains.add(get_domain(url_or_domain))

    def is_whitelisted(self, url_or_domain):
        return get_domain(url_or_domain) in self._domains

    @classmethod
    def load(cls, path="storage.pickles"):
        # also includes code to migrate to new format
        domains = []

        old_path = Path("whitelist.json")
        try:
            domains = json.loads(old_path.read_text())
            old_path.unlink()
        except FileNotFoundError:
            pass

        try:
            storage = pickle.load(Path(path).open("rb"))
        except FileNotFoundError:
            storage = Storage()

        for domain in domains:
            storage.whitelist(domain)

        return storage

    def save(self, path="storage.pickles"):
        with open(path, "wb") as f:
            pickle.dump(self, f)


def get_authorized_users(config, subreddit):
    conf_users = set(user.lower() for user in config.authorized_users)
    mods = set(mod.name.lower() for mod in subreddit.moderator())
    return conf_users | mods


def is_mention(inbox_item):
    return isinstance(inbox_item, praw.models.Comment) and inbox_item.subject == "username mention"


def main():
    config = from_json(Config, "config.json")
    reddit = reddit_from_conf(config)
    storage = Storage.load()
    subreddit = reddit.subreddit(config.subreddit)
    authorized_users = get_authorized_users(config, subreddit)
    replies = set()

    # mentions are usually bot commands
    mentions = list(filter(is_mention, reddit.inbox.unread(limit=None)))
    for mention in mentions:
        if "whitelist" in mention.body.lower():
            with print_block():
                printf("White listing request received")
                if mention.author.name.lower() not in authorized_users:
                    printf("User is not authorized to whitelist")
                    continue
                submission = mention.submission
                if not submission.is_self and not storage.is_whitelisted(submission.url):
                    storage.whitelist(submission.url)
                    printf("White listing {}", get_domain(submission.url))
                    process_submission(config, storage, submission, replies)
    reddit.inbox.mark_read(mentions)

    submissions = list(subreddit.new(limit=10))
    before = datetime.utcfromtimestamp(storage.before)
    for submission in submissions:
        created = datetime.utcfromtimestamp(submission.created_utc)
        if created > before:
            process_submission(config, storage, submission, replies)

    if len(submissions) > 0:
        storage.before = submissions[0].created_utc

    storage.save()


if __name__ == "__main__":
    main()
