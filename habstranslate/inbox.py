from praw.models import Comment

from .common import Task, printf, reddit_from_conf


class Inbox(Task):

    def __init__(self, config, whitelist):
        super().__init__(config, whitelist)

    def save_state(self):
        self._set.save()

    def run(self):
        reddit = reddit_from_conf(self._conf)
        subreddit = reddit.subreddit(self._conf['subreddit'])

        authorized_users = set(map(str.lower, self._conf.get('authorized_users', [])))

        for item in reddit.inbox.stream():
            reddit.inbox.mark_read([item])
            if not isinstance(item, Comment) and item.subject != 'username mention':
                continue
            if 'whitelist' in item.body.lower():
                printf("White listing request received")
                mods = set(mod.name.lower() for mod in subreddit.moderator())
                if item.author.name not in (authorized_users | mods):
                    printf("User is not authorized to whitelist\n------")
                    continue
                submission = item.submission
                if not submission.is_self and submission.url not in self._whitelist:
                    self._whitelist.add(submission.url)
                    self._whitelist.save()
                    printf("White listing {}", submission.url)
                    self.process_submission(submission)
