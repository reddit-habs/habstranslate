import re

import langdetect

_RE_SPLIT = re.compile(r"[\t\n\r\s]+")


def _twitter_elements(doc):
    return doc.find_all('p', class_='tweet-text')


def _elements(doc):
    return doc.find_all('p')


_DOMAIN_SELECTOR = {
    'twitter.com': _twitter_elements
}


def _select_elements(doc, domain):
    func = _DOMAIN_SELECTOR.get(domain, _elements)
    print("Using selector %s" % func.__name__)
    return func(doc)


def detect_lang(doc, domain):
    words = []
    for elem in _select_elements(doc, domain):
        text = elem.text
        for word in _RE_SPLIT.split(text):
            if len(word) > 0 and len(word) <= 25:
                words.append(word)
    all_text = ' '.join(words)
    return langdetect.detect(all_text)
