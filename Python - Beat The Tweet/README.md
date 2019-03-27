# Beat The Tweet
This is a fun little visualization/game I made to show what I can do with Python.  To run it on your system will require a Twitter Developer API key, which you can get for free from [Twitter](https://apps.twitter.com/) if you don't have one already.  Alternatively, [I've made a YouTube video tour of the program](https://youtu.be/B5bVpq8HzmM) if you would like to just review the code and watch a bit of the game in action.

# Installation

In addition to Python 3, Beat the Tweet requires three additional libraries:  pygame, tweepy, and textblob.

## Installing Pygame
Pygame is a python GUI wrapper package that allows easy sprite manipulation.  You can see the documentation at the [main site](http://www.pygame.org/), and [there are detailed instructions here](https://www.pygame.org/wiki/GettingStarted), or just install it yourself from the command line with:

$ pip install -U pygame --user

## Installing Tweepy
[Tweepy](http://docs.tweepy.org/en/v3.6.0/getting_started.html#hello-tweepy) is a Python package for connecting to the Twitter API.  Installation is simple from command line:

$ pip install tweepy

## Installing TextBlob
TextBlob is a great free tool for basic Natural Language Processing, but I’m just using it to run a simple sentiment analysis on the tweets.

$ pip install -U textblob

## Running Beat the Tweet - Windows
From the folder where BeatTheTweet.py resides:

$ python BeatTheTweet.py

## Running Beat the Tweet - Mac
Mac is a little more complicated.  Theoretically, since you installed with --user it should work with the same command as Windows, but some people report trouble with this.  You’ll know it’s a problem if the game screen doesn’t take focus and you can’t type or click anything.  If you’re running Anaconda, you can use the framework for a GUI program (note the ‘w’ at the end of ‘python’):

$ pythonw BeatTheTweet.py

If you’re not using Anaconda, you can try creating a virtual environment first:

$ python -m venv btt_venv
$ . test_venv/bin/activate
$ pip install pygame
$ pip install tweepy
$ pip install textblob
$ python BeatTheTweet.py

If that doesn’t work, [there are more details here](https://github.com/pygame/pygame/issues/203#issuecomment-365798598).

## Twitter API information
For the Twitter element to work, you will need to put your Twitter API key information in lines 35-38 of the Python code.
