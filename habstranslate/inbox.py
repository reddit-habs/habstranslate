from .common import Task, reddit_from_conf, printf

from praw.models import Comment


class Inbox(Task):

    def __init__(self, config, whitelist):
        super().__init__(config, whitelist)

    def save_state(self):
        self._set.save()

    def run(self):
        reddit = reddit_from_conf(self._conf)
        for item in reddit.inbox.stream():
            reddit.inbox.mark_read([item])
            if not isinstance(item, Comment) and item.subject != 'username mention':
                continue
            if 'whitelist' in item.body.lower():
                printf("White listing request received")
                if item.author.name not in self._conf['authorized_users']:
                    printf("User is not authorized to whitelist\n------")
                    continue
                submission = item.submission
                if not submission.is_self and submission.url not in self._whitelist:
                    self._whitelist.add(submission.url)
                    self._whitelist.save()
                    printf("White listing {}", submission.url)
                    self.process_submission(submission)
