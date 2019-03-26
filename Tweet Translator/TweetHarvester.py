from tweepy.streaming import StreamListener
from tweepy import OAuthHandler
from tweepy import Stream
import json
import time
import os, os.path
from urllib3.exceptions import ProtocolError
from queue import Queue
from threading import Thread

class TweetHarvester:
    def __init__(self):
        # Fire up the Twitter listener
        access_token = ""
        access_token_secret = ""
        consumer_key = ""
        consumer_secret = ""
        self.listener = TweetListener()
        self.latest_tweet = None
        self.tweetlist = []
        self.writeblock = 50  # Batch size of tweets before appending to JSON file
        self.minibatch = 0
        self.dir = 'H:/Data/w266_tweets/' # Directory to write files
        self.batchnum = len(
            [name for name in os.listdir(self.dir) if os.path.isfile(os.path.join(self.dir, name))])
        self.filename = "{}tweets{}.json".format(self.dir, self.batchnum)
        self.timer = 10  # Number of minutes to run the listener before completing the batch
        self.auth = OAuthHandler(consumer_key, consumer_secret)
        self.auth.set_access_token(access_token, access_token_secret)
        self.stream = Stream(self.auth, self.listener)
        #Initialize JSON file with an empty list
        with open(self.filename, 'w', encoding='utf-8') as f:
            f.write('[')

    def get_batches(self):
        tweetcounter = 0
        while tweetcounter < self.writeblock:
            if self.listener.latest_tweet is False:
                print("RATE-LIMITED, STOPPING STREAM")
                self.stream.disconnect()
                return False
            elif self.listener.latest_tweet is not None and self.listener.latest_tweet != self.latest_tweet:
                with open(self.filename, 'a', encoding='utf-8') as f:
                    json.dump(self.listener.latest_tweet, f)
                    f.write(',')
                #self.tweetlist.append(self.listener.latest_tweet)
                self.latest_tweet = self.listener.latest_tweet
                tweetcounter += 1
            else:
                pass
        else:
            #with open(self.filename, 'r+') as f:
            #   data = json.load(f)
            #data = data + self.tweetlist

            self.tweetlist = []
            self.minibatch += 1
            print("{} tweets harvested".format(self.writeblock * self.minibatch))
            return True

    def harvest(self):
        #self.stream.filter(locations=[-124.84, 24.39, -66.88, 49.38], languages=["en"],  async=True, stall_warnings=True)
        yelp_regions = [-113.30554, 32.786779, -110.833818, 34.236055,
                        -116.291936, 35.411708, -113.99976, 36.860984,
                        -80.378926, 42.986947, -78.483984, 44.436223,
                        -81.989433, 34.469949, -79.635921, 35.919225,
                        -82.631596, 40.667396, -80.630464, 42.116672,
                        -80.992748, 39.710791, -78.944274, 41.160067,
                        -74.50843, 44.791977, -72.688636, 46.241253,
                        -114.883557, 50.302235, -113.260277, 51.751511,
                        -90.314382, 42.358216, -88.391786, 43.807492,
                        -89.296007, 39.36964, -87.230105, 40.818916]
        self.stream.filter(locations=yelp_regions, languages=["en"], is_async=True, stall_warnings=True)
        time_end = time.time() + (self.timer * 60)
        while time.time() < time_end:
            if not self.get_batches():
                break
        else:
            with open(self.filename, 'a', encoding='utf-8') as f:
                f.seek(0, os.SEEK_END)
                f.seek(f.tell() - 1, os.SEEK_SET)
                f.truncate()
                f.write(']')
            self.stream.disconnect()
            print("BATCH FINISHED. {} TOTAL TWEETS HARVESTED.".format(self.writeblock * self.minibatch))
            time.sleep(2)
            return True

class TweetListener(StreamListener):
    """
    Open and maintain a persistent connection to the Twitter data stream.
    """
    def __init__(self, q=Queue()):
        StreamListener.__init__(self)
        self.latest_tweet = None
        self.q = q
        num_threads = 4
        '''
        for i in range(num_threads):
            t = Thread(target=self.move_tweets)
            t.daemon = True
            t.start()
        '''

    def on_data(self, data):
        """Parse tweets as they arrive."""
        tweet = json.loads(data)
        #if 'retweeted_status' not in tweet and 'quoted_status' not in tweet:
        self.latest_tweet = tweet
        #self.q.put(tweet)
        return True

    def on_error(self, status):
        """If the keyword triggers rate-limiting, stop and close listener."""
        if status == 420:
            self.latest_tweet = False
            return False

    def on_exception(self, exception):
        print(exception)
        return

    def move_tweets(self):
        while True:
            self.latest_tweet = self.q.get()
            self.q.task_done()

try:
    i = 0
    iterations = 50  # Number of Batches to fetch
    while i < iterations:
        tweets = TweetHarvester()
        tweets.harvest()
        i += 1
    else:
        print("ALL BATCHES COMPLETE")
except Exception as e:
    # traceback.print_exc(file=sys.stdout)
    print(e)