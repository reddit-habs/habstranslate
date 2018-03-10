from .common import Task, printf, reddit_from_conf


class Submissions(Task):

    def __init__(self, config, whitelist):
        super().__init__(config, whitelist)

    def save_state(self):
        self._set.save()

    def run(self):
        reddit = reddit_from_conf(self._conf)
        subreddit = reddit.subreddit(self._conf['subreddit'])

        for submission in subreddit.stream.submissions():
            printf("New submission on subreddit")
            self.process_submission(submission)
