#!/usr/bin/python2.7

import feedparser
import datetime
import dateutil.parser
import signal
import time
import tinyurl
import threading
import os
import traceback
from db import FeedDB
from config import Config

class FeedUpdater(object):

    def __init__(self, config, db):
        self.__config = config
        self.__db = db
        self.__threads = []

    def update_feeds(self, callback=None, forever=False):
        for feed in self.__db.get_feeds():
            t = threading.Thread(
                target=self.__fetch_feed,
                args=({
                    'id': feed[0],
                    'title': feed[1],
                    'url': feed[2],
                    'published': feed[3]
                }, callback, forever,
            ))
            t.start()
            self.__threads.append(t)

        if not forever:
            for thread in self.__threads:
                thread.join()
                self.__threads.remove(thread)

    def __fetch_feed(self, feed_info, callback, forever):
        """Fetches a RSS feed, parses it and updates the database and/or announces new news."""
        while 1:
            try:
                # check to see  if we should check feed or not
                if self.__db.is_chan_idle(self.__config.CHANNEL, self.__config.IDLE_MINUTES):
                    if not forever:
                        break
                    # sleep frequency minutes
                    time.sleep(int(feed_info['published'])*60)
                    continue

                # Parse a feed's url
                news = feedparser.parse( feed_info['url'] )

                # Reverse the ordering. Oldest first.
                for newsitem in news.entries[::-1]:
                    newstitle = newsitem.title
                    if self.__config.shorturls:
                        newsurl = tinyurl.create_one(newsitem.link) # Create a short link
                        if newsurl == "Error": #If that fails, use the long version
                            newsurl = newsitem.link
                    else:
                        newsurl = newsitem.link

                    # Try to get the published or updated date. Otherwise set it to 'no date'
                    try:
                        # Get date and parse it
                        newsdate = dateutil.parser.parse(newsitem.published)
                        # Format date based on 'dateformat' in config.py
                        newsdate = newsdate.strftime(self.__config.dateformat)

                    except Exception, e:
                        try:
                            # Get date and parse it
                            newsdate = dateutil.parser.parse(newsitem.updated)
                            # Format date based on 'dateformat' in config.py
                            newsdate = newsdate.strftime(self.__config.dateformat)

                        except Exception as e:
                            newsdate = "no date"

                    # Update the database. If it's a new issue, post it to the channel
                    is_new = self.__db.insert_news(feed_info['id'], newstitle, newsitem.link, newsdate)
                    if is_new and callback is not None:
                        callback(feed_info['title'], newstitle, newsurl, newsdate)
                print "Updated: " + feed_info['title']
            except Exception as e:
                tb = traceback.format_exc()
                print e, tb
                print "__fetch_feed title: {} error {} \n {}".format(
                    feed_info['title'], e, tb)

            if not forever:
                break

            # sleep frequency minutes
            time.sleep(int(feed_info['published'])*60)

if __name__ == "__main__":
    def print_line(feed_title, news_title, news_url, news_date):
        print("[+]: {}||{}||{}||{}".format(feed_title, news_title, news_url, news_date))

    def main():
        config = Config()
        db = FeedDB(config)
        updater = FeedUpdater(config, db)

        updater.update_feeds(print_line, False)

    def signal_handler(signal, frame):
        print "Caught SIGINT, terminating."
        os._exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    main()
