import json
from .common import Whitelist
from .inbox import Inbox
from .submissions import Submissions


def main():
    with open('config.json') as f:
        config = json.load(f)

        whitelist = Whitelist()

        tasks = [Inbox(config, whitelist), Submissions(config, whitelist)]
        for t in tasks:
            t.start()
        try:
            for t in tasks:
                t.join()
        except KeyboardInterrupt:
            whitelist.save()


if __name__ == '__main__':
    main()
