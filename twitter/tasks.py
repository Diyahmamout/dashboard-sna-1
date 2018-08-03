from __future__ import absolute_import, unicode_literals
from celery import shared_task
from .collect_tweet import Main

@shared_task
def crawl_data(params):
	event = Main()
	event.stream(tweet_method=params[0], keywords=params[1], lan_code=params[2], locations=params[3], user_id=params[4], table=params[5], consumer_key=params[6], consumer_secret=params[7], access_token=params[8], access_token_secret=params[9], category=params[10])
