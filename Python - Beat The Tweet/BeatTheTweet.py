from random import *
import os
import json
import time
from pathlib import Path
from datetime import timedelta
import sys
import traceback
try:
    import pygame.freetype
    import pygame
    from tweepy.streaming import StreamListener
    from tweepy import OAuthHandler
    from tweepy import Stream
    from textblob import TextBlob
except ImportError as e:
    print("PyGame, Tweepy, and TextBlob must be installed for Beat the Tweet to function.\n", e)


class GameBase:
    """
    The primary game class, it holds top-level game variables and runs the game engine.
    """
    def __init__(self):
        self.next = self
        # Display variables
        self.colors = {'bg': (0, 0, 0), 'hudbg': (60, 60, 60), 'dark': (35, 35, 35), 'white': (255, 255, 255),
                       'red': (163, 21, 21), 'tweetblue': (100, 100, 255)}
        self.w, self.h = 0, 0
        # Dictionaries to store images, fonts, etc.
        self.image_library, self.cached_fonts, self.cached_text = {}, {}, {}
        # Ship and gameplay variables
        self.mobility, self.alert = 5, None
        # Fire up the Twitter listener
        #
        # ENTER TWITTER API INFORMATION HERE
        #
        access_token = ""
        access_token_secret = ""
        consumer_key = ""
        consumer_secret = ""
        self.listener = TweetListener()
        self.auth = OAuthHandler(consumer_key, consumer_secret)
        self.auth.set_access_token(access_token, access_token_secret)
        self.stream = Stream(self.auth, self.listener)

    def process_input(self, events, pressed_keys):
        """ Process keyboard and mouse events that have accumulated in the event list since last frame."""
        pass    # Overridden in child classes

    def update(self):
        """ Update game logic."""
        pass    # Overridden in child classes

    def render(self, screen):
        """ Black out the screen and render new objects in order from back to front. """
        pass    # Overridden in child classes

    def switch_to_scene(self, next_scene):
        """ Moves between scenes, and closes the game if passed None."""
        self.next = next_scene

    def terminate(self):
        """ Force quit the game."""
        self.alert = "Exiting, Please Wait..."
        self.stream.disconnect()
        sys.stdout.flush()
        os._exit(0)

    def get_image(self, path):
        """ Retrieve image from cache.  If it isn't there yet, get it from disk and put it there."""
        image = self.image_library.get(path)
        if image is None:   # Retrieve image from disc correctly for Windows or Mac
            canonicalized_path = path.replace('/', os.sep).replace('\\', os.sep)
            image = pygame.image.load(canonicalized_path)
            self.image_library[path] = image
        return image

    @staticmethod
    def run_game(width, height, fps, starting_scene):
        """ Initialize the Pygame instance, start the clock and open the first scene.
        Listen for events and call the sub-classes to update and render. """
        pygame.init()
        screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
        clock = pygame.time.Clock()
        active_scene = starting_scene(width, height)

        # The loop that holds the game
        while active_scene is not None:
            pressed_keys = pygame.key.get_pressed()
            # Filter for keyboard or mouse events
            filtered_events = []
            for event in pygame.event.get():
                quit_attempt = False
                # Manage all the potential ways to exit the game
                if event.type == pygame.QUIT:
                    quit_attempt = True
                elif event.type == pygame.KEYDOWN:
                    alt_pressed = pressed_keys[pygame.K_LALT] or \
                                  pressed_keys[pygame.K_RALT]
                    if event.key == pygame.K_ESCAPE:
                        quit_attempt = True
                    elif event.key == pygame.K_F4 and alt_pressed:
                        quit_attempt = True
                if quit_attempt:
                    active_scene.terminate()
                else:
                    # Collect a list of all events that have happened since the last loop
                    filtered_events.append(event)
            # Pass those events to the active scene
            active_scene.process_input(filtered_events, pressed_keys)
            # Update the game logic within the scene
            active_scene.update()
            # Refresh and redraw the screen elements
            active_scene.render(screen)
            # Are we still in this scene?
            active_scene = active_scene.next
            # Flip the display to the newly-rendered scene
            pygame.display.flip()
            # Tick to the next frame
            clock.tick(fps)

    @staticmethod
    def make_font(font, size):
        """ Build the font object for making text.  Check first if the font is a system font,
        then check if there's a custom path to the desired font, otherwise use default. """
        available = pygame.font.get_fonts()
        if font.lower() in available:
            return pygame.freetype.SysFont(font.lower(), size)
        elif Path(font).is_file():
            return pygame.freetype.Font(font, size)
        else:
            return pygame.freetype.Font(None, size)

    def get_font(self, font_rank, size):
        """ Determine if the font to make this text is in the cache.  If not, send to make_font to retrieve it."""
        fonts = {1: 'resources/NotoSans-Thin.ttf', 2: 'resources/NotoSans-ExtraLight.ttf',
                 3: 'resources/NotoSans-Light.ttf', 4: 'resources/NotoSans-Regular.ttf',
                 5: 'resources/NotoSans-Medium.ttf', 6: 'resources/NotoSans-SemiBold.ttf',
                 7: 'resources/NotoSans-Bold.ttf', 8: 'resources/NotoSans-ExtraBold.ttf',
                 9: 'resources/NotoSans-Black.ttf', 10: 'ArialBlack'}
        key = str(fonts[font_rank]) + '|' + str(size)
        font = self.cached_fonts.get(key, None)
        if font is None:
            font = self.make_font(fonts[font_rank], size)
            self.cached_fonts[key] = font
        return font

    def create_text(self, text, rank, size, color, bg):
        """ Determine if the rendered image of this text is in the cache and return it.  If not, make a new one."""
        key = '|'.join(map(str, (rank, size, color, text)))
        image = self.cached_text.get(key, None)
        if image is None:
            font = self.get_font(rank, size)
            image = font.render(text, color, bg)
            self.cached_text[key] = image
        return image

    @staticmethod
    def scaler(f, old, new):
        """ Convert integer f from place in range [oldmin, oldmax] to corresponding value in range [newmin, newmax] """
        oldmn, oldmx = old[0], old[1]
        mn, mx = new[0], new[1]
        new_range, old_range = mx-mn, oldmx-oldmn
        if f > oldmx:
            newf = oldmx
        elif f < oldmn:
            newf = oldmn
        else:
            newf = f
        return int((((newf - oldmn) * new_range) / old_range) + mn)

    def colorizer(self, score):
        """ Accept a score between -1 and 1.  If < 0, use number to scale Red, if > 0, use number to scale Green."""
        score = float(score) if type(score) != int else score
        base_color = self.colors['tweetblue']
        newc = self.scaler(abs(score), [0, 1], [0, 255])
        new_color = (base_color[0], newc, base_color[2]) if score > 0 else (newc, base_color[1], base_color[2])
        return new_color


class TitleScene(GameBase):
    """
    Manage the intro scene:  display instructions, receive keyword and configs, display high scores.
    """
    def __init__(self, w, h):
        GameBase.__init__(self)
        self.keyword = ''
        pygame.mouse.set_visible(True)
        pygame.event.set_grab(False)
        self.w, self.h = w, h
        self.input = pygame.Rect(self.w / 2 - (self.w * .4) / 2, self.h * .25, self.w * .4, 40)
        self.imm = pygame.Rect(self.w * .55, self.h * .41, 16, 16)
        self.mouse = pygame.Rect(self.imm.left, self.imm.bottom + 10, 16, 16)
        self.input_active, self.imm_active, self.mouse_active, self.alert = True, False, False, None
        self.demo_ship = Ship(location=[self.w*.02+5, self.h*.4-9], speed=[0, 0])
        self.tweet_display = self.create_text("This is a Tweet.", 6, int(self.h * .05),
                                              self.colors['tweetblue'], self.colors['bg'])[0]
        self.tweet_rect = self.tweet_display.get_rect(top=self.h * .58, left=self.w * .02 + 50)
        if Path('scores.json').is_file():
            with open('scores.json') as f:
                self.highscore = json.load(f)
                self.killtweet = Tweet({'text': self.highscore['top']['text'], 'followers': 400,
                                        'user': self.highscore['top']['user'],
                                        'engagement': self.highscore['top']['engagement'],
                                        'sentiment': self.highscore['top']['sentiment']}, title=True)
        else:
            self.highscore, self.killtweet = None, None

    def process_input(self, events, pressed_keys):
        for event in events:
            if event.type == pygame.KEYDOWN and self.input_active:
                self.alert = None
                self.keyword = self.keyword[:-1] if event.key == pygame.K_BACKSPACE else self.keyword + event.unicode
            if event.type == pygame.KEYDOWN and event.key == pygame.K_TAB:
                self.input_active = not self.input_active
            if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                self.keyword = self.keyword[:-1] if self.input_active else self.keyword
                if len(self.keyword) > 2:
                    self.switch_to_scene(GameScene(self.keyword, not self.imm_active, self.mouse_active))
                else:
                    self.alert = "Please enter a keyword of three or more characters."
            if event.type == pygame.VIDEORESIZE:
                pygame.display.set_mode(event.dict['size'], pygame.RESIZABLE)
                self.w, self.h = event.dict['w'], event.dict['h']
                self.input = pygame.Rect(self.w / 2 - (self.w * .4) / 2, self.h * .25, self.w * .4, 40)
                self.demo_ship.shiprect.left, self.demo_ship.shiprect.top = self.w*.02+5, self.h*.4-9
                self.tweet_rect = self.tweet_display.get_rect(top=self.h * .58, left=self.w * .02 + 50)
                self.imm = pygame.Rect(self.w * .55, self.h * .44, 16, 16)
                self.mouse = pygame.Rect(self.imm.left, self.imm.bottom + 10, 16, 16)
            if event.type == pygame.MOUSEBUTTONDOWN:
                if self.input.collidepoint(event.pos):
                    self.input_active = not self.input_active
                else:
                    self.input_active = False
                if self.imm.collidepoint(event.pos):
                    self.imm_active = not self.imm_active
                if self.mouse.collidepoint(event.pos):
                    self.mouse_active = not self.mouse_active

    def render_text(self, screen):
        """ Display all of the text elements of the page, as well as the masks for scrolling text."""
        pygame.draw.rect(screen, self.colors['tweetblue'], (0, 0, self.w, self.h*.17), 0)
        pygame.draw.line(screen, self.colors['white'], (0, self.h*.17), (self.w, self.h*.17), 1)
        pygame.draw.rect(screen, self.colors['bg'], (self.w * .48, self.h*.58, self.w/2, self.h * .07))
        pygame.draw.rect(screen, self.colors['bg'], (0, self.h * .58, self.w*.02 + 50, self.h * .07))
        pygame.draw.rect(screen, self.colors['bg'], (0, self.h * .79, self.w * .55, self.h * .08), 0)
        pygame.draw.rect(screen, self.colors['bg'], (self.w * .95, self.h * .79, self.w * .05, self.h * .08), 0)
        title = "BEAT THE TWEET"
        title_display = self.create_text(title, 10, int(self.h*.12), self.colors['bg'], self.colors['tweetblue'])[0]
        title_rect = title_display.get_rect(center=(self.w / 2, self.h*.09))
        screen.blit(title_display, title_rect)
        t1 = "Type a search term and press [Enter] to start:"
        t1_display = self.create_text(t1, 7, int(self.h*.025), self.colors['white'], self.colors['bg'])[0]
        t1_rect = t1_display.get_rect(center=(self.w / 2, self.h*.22))
        screen.blit(t1_display, t1_rect)
        t2 = "This is you."
        t2_display = self.create_text(t2, 8, int(self.h*.025), self.colors['white'], self.colors['bg'])[0]
        t2_rect = t2_display.get_rect(top=self.h*.4, left=self.w*.02 + 50)
        screen.blit(t2_display, t2_rect)
        t3 = ["You can rotate with the arrow keys, [A] & [D] or the mouse.",
              "[Space], [Up], [W] or the Left Mouse Button will accelerate.",
              "Numbers [1]-[0] or mousewheel changes your mobility level.",
              "There are no brakes."]
        for line in range(0, len(t3)):
            line_display = self.create_text(t3[line], 5, int(self.h*.02), self.colors['white'], self.colors['bg'])[0]
            line_rect = line_display.get_rect(top=self.h*.41+((line+1)*self.h*.027), left=self.w*.02 + 50)
            screen.blit(line_display, line_rect)
        t4 = ["Tweets matching your search term will appear in real-time.",
              "Tweets' speed, size, weight, and color change according to",
              "their length, engagement, # of followers, and sentiment.",
              "Touching a Tweet will kill you.  Difficulty scales according",
              "to the popularity of the search term you choose: 'python'",
              "is pretty easy; 'Trump' is suicide."]
        for line in range(0, len(t4)):
            line_display = self.create_text(t4[line], 5, int(self.h*.02), self.colors['white'], self.colors['bg'])[0]
            line_rect = line_display.get_rect(top=self.h*.62+((line+1)*self.h*.027), left=self.w*.02 + 50)
            screen.blit(line_display, line_rect)
        c = ["[Backspace] to return to Title Screen", "[ESC] to Quit the game."]
        for line in range(0, len(c)):
            line_display = self.create_text(c[line], 8, int(self.h*.025), self.colors['white'], self.colors['bg'])[0]
            line_rect = line_display.get_rect(top=self.h*.81+((line+1)*self.h*.033), left=self.w*.02 + 50)
            screen.blit(line_display, line_rect)
        pygame.draw.rect(screen, self.colors['red'], (0, self.h*.92+3, self.w, self.h*.05))
        footer = "The goal is to survive as long as you can."
        footer_display = self.create_text(footer, 10, int(self.h*.04), self.colors['bg'], self.colors['red'])[0]
        footer_rect = footer_display.get_rect(center=(self.w / 2, self.h*.95))
        screen.blit(footer_display, footer_rect)

    def render_score(self, screen):
        """ Display the user's high score and score history."""
        sb = pygame.draw.rect(screen, self.colors['white'], (self.w * .55, self.h * .6, self.w * .4, self.h * .27), 1)
        sbt = pygame.draw.rect(screen, self.colors['tweetblue'], (sb.left+1, sb.top+1, sb.width-2, self.h * .052), 0)
        sbtext = self.create_text("HIGH SCORE", 7, int(self.h * .025), self.colors['bg'], self.colors['tweetblue'])[0]
        sbtext_rect = sbtext.get_rect(center=(sbt.centerx, sbt.centery))
        screen.blit(sbtext, sbtext_rect)
        if self.highscore is not None:
            counter = 1
            for key, value in self.highscore['top'].items():
                if counter < 6:
                    scoreline = key + " " + str(value)
                    line_display = self.create_text(scoreline, 5, int(self.h * .02),
                                                    self.colors['white'], self.colors['bg'])[0]
                    line_rect = line_display.get_rect(top=self.h*.65+(counter*self.h*.025), left=self.w * .55 + 10)
                    screen.blit(line_display, line_rect)
                counter += 1
            dtweet = "The tweet that killed you, courtesy of @"+self.highscore['top']['user']
            dtweet_text = self.create_text(dtweet, 5, int(self.h * .015), self.colors['white'], self.colors['bg'])[0]
            dtweet_rect = dtweet_text.get_rect(right=sb.right-10, bottom=sb.bottom-5)
            screen.blit(dtweet_text, dtweet_rect)
        else:
            s = pygame.draw.rect(screen, self.colors['red'],
                                 (sb.left + 1, sb.top + sb.height*.44, sb.width-2, self.h * .052), 0)
            score = "NO SCORE YET"
            score_display = self.create_text(score, 7, int(self.h * .025), self.colors['white'], self.colors['red'])[0]
            score_rect = score_display.get_rect(center=(s.centerx, s.centery))
            screen.blit(score_display, score_rect)

    def render_input(self, screen):
        """ Display the textbox and checkboxes. """
        if self.input_active:
            pygame.draw.rect(screen, self.colors['white'], self.input, 0)
            pygame.draw.rect(screen, self.colors['tweetblue'], self.input, 2)
        else:
            pygame.draw.rect(screen, (230, 230, 240), self.input, 0)
            pygame.draw.rect(screen, self.colors['hudbg'], self.input, 2)
        keyword_display = self.create_text(self.keyword, 6, 30, self.colors['bg'], None)[0]
        keyword_rect = keyword_display.get_rect(center=(self.w/2, self.h*.25+20))
        screen.blit(keyword_display, keyword_rect)
        # Draw the cursor
        if self.input_active and time.time() % 1 < .5:
            pygame.draw.line(screen, self.colors['bg'], (keyword_rect.right, self.h*.25+8),
                             (keyword_rect.right, self.h*.25+32), 1)
        # Draw the checkboxes and label
        pygame.draw.rect(screen, self.colors['white'], self.imm, 0)
        imm = "Immortal mode (just watch the tweets)"
        imm_display = self.create_text(imm, 4, int(self.h * .018), self.colors['white'], self.colors['bg'])[0]
        imm_rect = imm_display.get_rect(left=self.imm.right+10, top=self.imm.top+3)
        screen.blit(imm_display, imm_rect)
        if self.imm_active:
            pygame.draw.line(screen, self.colors['bg'], (self.imm.left, self.imm.top),
                             (self.imm.right, self.imm.bottom), 1)
            pygame.draw.line(screen, self.colors['bg'], (self.imm.left, self.imm.bottom),
                             (self.imm.right, self.imm.top), 1)
        pygame.draw.rect(screen, self.colors['white'], self.mouse, 0)
        mouse = "Enable mouse control (mouse pointer will disappear in game)"
        mouse_display = self.create_text(mouse, 4, int(self.h * .018), self.colors['white'], self.colors['bg'])[0]
        mouse_rect = mouse_display.get_rect(left=self.mouse.right+10, top=self.mouse.top+3)
        screen.blit(mouse_display, mouse_rect)
        if self.mouse_active:
            pygame.draw.line(screen, self.colors['bg'], (self.mouse.left, self.mouse.top),
                             (self.mouse.right, self.mouse.bottom), 1)
            pygame.draw.line(screen, self.colors['bg'], (self.mouse.left, self.mouse.bottom),
                             (self.mouse.right, self.mouse.top), 1)

    def render_alert(self, alert, screen):
        """ Display the alert box over the input box."""
        pygame.draw.rect(screen, self.colors['red'], (0, self.h*.19, self.w, self.h*.052), 0)
        pygame.draw.line(screen, self.colors['white'], (0, self.h*.19), (self.w, self.h*.19), 1)
        pygame.draw.line(screen, self.colors['white'], (0, self.h*.19+self.h*.052), (self.w, self.h*.19+self.h*.052), 1)
        alert_display = self.create_text(alert, 7, int(self.h*.025), self.colors['white'], self.colors['red'])[0]
        alert_rect = alert_display.get_rect(center=(self.w / 2, self.h*.22))
        screen.blit(alert_display, alert_rect)

    def update(self):
        self.demo_ship.rotate(-1, 2)
        if self.tweet_rect.right < 10:
            self.tweet_rect.left = self.w*.5
            self.tweet_display = self.create_text("This is a Tweet.", randint(1, 8), randint(25, 50),
                                                  self.colorizer(uniform(-1, 1)), self.colors['bg'])[0]
        self.tweet_rect = self.tweet_rect.move([-3, 0])
        if self.killtweet is not None:
            self.killtweet.tweetrect.top = self.h * .81
            if self.killtweet.tweetrect.right < self.w * .55:
                self.killtweet.tweetrect.left = self.w * .95
            self.killtweet.update_tweet()

    def render(self, screen):
        screen.fill(self.colors['bg'])
        screen.blit(self.tweet_display, self.tweet_rect)
        if self.killtweet is not None:
            self.killtweet.render_tweet(screen)
        self.render_text(screen)
        self.render_score(screen)
        self.demo_ship.render_ship(screen)
        if self.alert is not None:
            self.render_alert(self.alert, screen)
        self.render_input(screen)


class GameScene(GameBase):
    """
    Manage the game scene:  display ship, tweets, and heads-up display.  Monitor for events and update accordingly.
    """
    def __init__(self, keyword, mortal, mouse):
        GameBase.__init__(self)
        self.keyword = keyword
        self.mortal = mortal
        self.mouse = mouse
        self.player_ship = Ship(location=[50, 200], speed=[1, 0])
        if self.mouse:  # If mouse control enabled, hide the pointer and grab position information from mouse.
            pygame.mouse.set_visible(False)
            pygame.event.set_grab(True)
        self.tweetlist, self.tweetcount = [], 0
        self.dead, self.controls = False, False
        self.latest_tweet, self.start_time = None, None
        screen = pygame.display.get_surface().get_size()
        self.w, self.h = screen[0], screen[1]
        self.score = None if self.mortal else "IMMORTAL"

    def check_tweets(self):
        """ Check to see if there is a new tweet. If there is, put make a new Tweet object and put it in the
        tweetlist, and update the the most recent tweet variable to reflect it. """
        if self.listener.latest_tweet is False:
            self.death("RATE-LIMITING: TRY AGAIN LATER")
        elif self.listener.latest_tweet is not None and self.listener.latest_tweet != self.latest_tweet:
            self.tweetlist.append(Tweet(self.listener.latest_tweet))
            self.latest_tweet = self.listener.latest_tweet
        else:
            pass

    def reset_game(self):
        """ If user comes back for more than one game, set all variables to starting state."""
        self.tweetlist = []
        self.start_time = 0.0
        self.latest_tweet = None
        self.tweetcount = 0
        self.score = None if self.mortal else "IMMORTAL"
        self.stream.filter(track=[self.keyword], async=True)

    def death(self, message, tweet=None, user=None, color=None, weight=None):
        """ Upon death: close the stream, post a message to screen, and record score to JSON file."""
        self.dead = True
        self.stream.disconnect()
        self.alert = message
        self.score = str(timedelta(self.start_time, time.clock()))[:-4]
        tpm = round((self.tweetcount/timedelta(self.start_time, time.clock()).seconds)*60, 2) \
            if timedelta(self.start_time, time.clock()).seconds > 0 else 0
        if self.mortal and message != "QUITTER.":
            scorefile = Path('scores.json')
            scorecard = {'Date:': time.asctime(time.localtime()), 'Keyword:': self.keyword,
                         '# Tweets:': self.tweetcount, 'Survival Time:': self.score, 'TPM': tpm, 'text': tweet,
                         'user': user, 'sentiment': color, 'engagement': weight}
            if scorefile.is_file():  # If a top score already exists, check to see if it needs to be updated.
                with open('scores.json') as f:
                    scores = json.load(f)
                    this_score = {len(scores)+1: scorecard}
                    if scorecard['# Tweets:'] > scores['top']['# Tweets:']:
                        scores['top'] = scorecard
                    scores.update(this_score)
            else:
                    scores = {'top': scorecard, 2: scorecard}
            with open('scores.json', 'w') as f:  # Write this score regardless of whether it is top or not.
                json.dump(scores, f)

    def process_input(self, events, pressed_keys):
        """ Process keyboard and mouse events that have accumulated in the event list since last frame."""
        for event in events:
            # Exit events
            if event.type == pygame.KEYDOWN and event.key == pygame.K_BACKSPACE and not self.dead:
                self.death("QUITTER.")
            if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN and self.dead:
                self.switch_to_scene(TitleScene(self.w, self.h))
            # Ship mobility
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 4:
                if self.mobility < 10:
                    self.mobility += 1
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 5:
                if self.mobility > 1:
                    self.mobility -= 1
            if event.type == pygame.KEYDOWN and event.key == pygame.K_1:
                self.mobility = 1
            if event.type == pygame.KEYDOWN and event.key == pygame.K_2:
                self.mobility = 2
            if event.type == pygame.KEYDOWN and event.key == pygame.K_3:
                self.mobility = 3
            if event.type == pygame.KEYDOWN and event.key == pygame.K_4:
                self.mobility = 4
            if event.type == pygame.KEYDOWN and event.key == pygame.K_5:
                self.mobility = 5
            if event.type == pygame.KEYDOWN and event.key == pygame.K_6:
                self.mobility = 6
            if event.type == pygame.KEYDOWN and event.key == pygame.K_7:
                self.mobility = 7
            if event.type == pygame.KEYDOWN and event.key == pygame.K_8:
                self.mobility = 8
            if event.type == pygame.KEYDOWN and event.key == pygame.K_9:
                self.mobility = 9
            if event.type == pygame.KEYDOWN and event.key == pygame.K_0:
                self.mobility = 10
            if event.type == pygame.KEYDOWN and event.key == pygame.K_c:
                self.controls = not self.controls
        # Steering
        keystate = pygame.key.get_pressed()
        direction = (keystate[pygame.K_LEFT] + keystate[pygame.K_a]) - (keystate[pygame.K_RIGHT] + keystate[pygame.K_d])
        if not self.dead:
            self.player_ship.rotate(direction, self.mobility)
        # Acceleration
        if keystate[pygame.K_SPACE] or keystate[pygame.K_UP] or keystate[pygame.K_w]:
            self.player_ship.move(self.mobility)
        if self.mouse:       # Mouse control
            mousestate = pygame.mouse.get_pressed()
            if mousestate[0]:
                self.player_ship.move(self.mobility)
            mousemove = pygame.mouse.get_rel()
            if mousemove[0] != 0 and not self.dead:
                self.player_ship.rotate(mousemove[0]/100, self.mobility)

    def render_back(self, screen):
        """ Render the background layer."""
        keyword = self.keyword
        keyword_display = self.create_text(keyword, 9, 100, self.colors['dark'], None)[0]
        keyword_rect = keyword_display.get_rect(center=(self.w/2, self.h/2 - 18))
        screen.blit(keyword_display, keyword_rect)

    def render_hud(self, screen):
        """ Render the Heads-Up Display."""
        bar = pygame.draw.rect(screen, self.colors['hudbg'], (0, self.h - (self.h*.07), self.w, self.h*.07), 0)
        pygame.draw.line(screen, self.colors['white'], (0, self.h - (self.h*.07)), (self.w, self.h - (self.h*.07)), 1)
        ctog = "Press [C] to toggle control display"
        ctog_display = self.create_text(ctog, 4, int(self.h * .02), self.colors['white'], None)[0]
        ctog_rect = ctog_display.get_rect(centerx=self.w/2, top=bar.top-20)
        screen.blit(ctog_display, ctog_rect)
        if self.controls:
            if self.mouse:
                controls = ['Rotate: [A][D], [<-][->] or mouse', 'Accelerate: [W], [Space], [Up] or mousebutton',
                            'Set Mobility: numbers [1-0] or mousewheel', 'Return to Title: [Backspace]', 'Quit: [Esc]']
            else:
                controls = ['Rotate: [A][D], [<-][->]', 'Accelerate: [W], [Space], or [Up]',
                            'Set Mobility: numbers [1-0]', 'Return to Title: [Backspace]', 'Quit: [Esc]']
            for c in range(0, len(controls)):
                c_display = self.create_text(controls[c], 4, int(self.h * .02), self.colors['white'], None)[0]
                c_rect = c_display.get_rect(top=20+((c+1)*self.h*.027), left=20)
                screen.blit(c_display, c_rect)
        timer = self.score if self.score is not None else str(timedelta(self.start_time, time.clock()))[:-4]
        timer_display = self.create_text(timer, 10, int(self.h*.03), self.colors['white'], self.colors['hudbg'])[0]
        timer_rect = timer_display.get_rect(left=self.w-(self.w*.15), top=self.h-(self.h*.045))
        screen.blit(timer_display, timer_rect)
        status = "Mobility Level: "+str(self.mobility)
        status_display = self.create_text(status, 5, int(self.h*.03), self.colors['white'], self.colors['hudbg'])[0]
        status_rect = status_display.get_rect(left=self.w*.02, top=self.h - (self.h*.045))
        screen.blit(status_display, status_rect)
        tweetcount = "Tweet Count: "+str(self.tweetcount) if self.tweetcount > 0 else "Waiting for a Tweet..."
        tweetcount_display = self.create_text(tweetcount, 5, int(self.h*.03),
                                              self.colors['white'], self.colors['hudbg'])[0]
        tweetcount_rect = tweetcount_display.get_rect(centerx=(self.w/2), top=self.h - (self.h*.045))
        screen.blit(tweetcount_display, tweetcount_rect)

    def render_alert(self, alert, screen):
        """ Render the alert message upon quitting or death."""
        pygame.draw.rect(screen, self.colors['red'], (0, self.h / 2 - 40, self.w, 80), 0)
        pygame.draw.line(screen, self.colors['white'], (0, self.h / 2 - 40), (self.w, self.h / 2 - 40), 1)
        pygame.draw.line(screen, self.colors['white'], (0, self.h / 2 + 40), (self.w, self.h / 2 + 40), 1)
        alert_display = self.create_text(alert, 10, 40, self.colors['white'], self.colors['red'])[0]
        if self.dead:
            alert_rect = alert_display.get_rect(center=(self.w / 2, self.h / 2 - 9))
            subalert = "Press [Enter] to return to the Title Screen"
            subalert_display = self.create_text(subalert, 5, 15, self.colors['white'], self.colors['red'])[0]
            subalert_rect = subalert_display.get_rect(center=(self.w / 2, self.h / 2 + 23))
            screen.blit(subalert_display, subalert_rect)
        else:
            alert_rect = alert_display.get_rect(center=(self.w / 2, self.h / 2))
        screen.blit(alert_display, alert_rect)

    def update(self):
        if self.start_time is None:   # Upon reloading the screen, wipe the slate clean
            self.reset_game()
        if not self.dead:    # Freeze all logic upon death
            self.player_ship.update_ship()
            self.check_tweets()
            for tweet in self.tweetlist:
                if tweet.kill_tweet():  # Purge tweetlist of tweets that have passed
                    self.tweetlist.remove(tweet)
                    self.tweetcount += 1
                else:
                    tweet.update_tweet()
                if self.mortal and tweet.kill_player(self.player_ship.shiprect):  # Monitor for death
                    self.death("DEATH BY TWEET", tweet.text, tweet.user, tweet.sentiment, tweet.engagement)

    def render(self, screen):
        screen.fill(self.colors['bg'])
        self.render_back(screen)
        self.player_ship.render_ship(screen)
        for tweet in self.tweetlist:
            tweet.render_tweet(screen)
        self.render_hud(screen)
        if self.alert is not None:
            self.render_alert(self.alert, screen)


class Ship(GameBase):
    """
    A class for the player's ship.  Manage controls, update screen position and display.
    """
    def __init__(self, location, speed):
        GameBase.__init__(self)
        self.ship = self.get_image("resources/o.png")
        screen = pygame.display.get_surface().get_size()
        self.w, self.h = screen[0], screen[1]
        self.shiprect = self.ship.get_rect(left=location[0], top=location[1])
        self.shipangle = 0
        self.speed = speed

    def rotate(self, anglemod, mobility):
        """ Rotate the ship around its center, keeping the angle between 0 and 359"""
        anglemod *= mobility   # Modifier to set how quickly the ship turns
        if self.shipangle + anglemod > 359:  # Ensure angle stays between 0 and 359
            newangle = 0
        elif self.shipangle + anglemod < 0:
            newangle = 359
        else:
            newangle = self.shipangle + anglemod
        # Pull a fresh image from the cache on every turn (to prevent pixel decay)
        ship = self.get_image("resources/o.png")
        rot_image = pygame.transform.rotate(ship, newangle)
        rot_rect = self.shiprect.copy()
        rot_rect.center = rot_image.get_rect().center
        rot_image = rot_image.subsurface(rot_rect).copy()
        # Update the ship's image and angle
        self.ship = rot_image
        self.shipangle = newangle

    def move(self, mobility):
        """ Accelerates the ship on a vector opposite its angle, keeping speed below the max_speed. """
        a = self.shipangle
        acc_rate = mobility*.03    # Modifier to set how quickly the ship accelerates
        max_speed = mobility
        # Use ship angle to determine how quickly to accelerate on the y-axis
        if 0 <= a <= 180:
            y = acc_rate * (((1 / 90) * a) - 1)
        else:
            y = acc_rate * (((-1 / 90) * a) + 3)
        # Use ship angle to determine how quickly to accelerate on the x-axis
        if 0 <= a <= 90:
            x = acc_rate * (((-1 / 90) * a) + 0)
        elif 90 < a <= 270:
            x = acc_rate * (((1 / 90) * a) - 2)
        else:
            x = acc_rate * (((-1 / 90) * a) + 4)
        # Keep ship within speed limit for x-axis
        if self.speed[0] > max_speed:
            self.speed[0] = max_speed
        elif self.speed[0] < -max_speed:
            self.speed[0] = -max_speed
        else:
            self.speed[0] += x
        # Keep ship within speed limit for y-axis
        if self.speed[1] > max_speed:
            self.speed[1] = max_speed
        elif self.speed[1] < -max_speed:
            self.speed[1] = -max_speed
        else:
            self.speed[1] += y

    def update_ship(self):
        """ Update the position of the ship according to its current speed."""
        shiprect = self.shiprect.move(self.speed)
        # Manage flying through the walls
        shiprect.left = self.w if shiprect.right < 10 else shiprect.left
        shiprect.bottom = 10 if shiprect.top > self.h-40 else shiprect.bottom
        shiprect.right = 10 if shiprect.left > self.w else shiprect.right
        shiprect.top = self.h-40 if shiprect.bottom < 10 else shiprect.top
        self.shiprect = shiprect.move(self.speed)

    def render_ship(self, screen):
        """ Display the ship in its new location."""
        screen.blit(self.ship, self.shiprect)


class Tweet(GameScene):
    """
    A class for each tweet that matches the keyword.  Attributes are determined by elements within the tweet.
    """
    def __init__(self, tweet_dict, keyword=None, mortal=None, title=False, mouse=False):
        GameScene.__init__(self, keyword, mortal, mouse)
        screen = pygame.display.get_surface().get_size()
        self.w, self.h = screen[0], screen[1]
        if title:
            pygame.mouse.set_visible(True)
            pygame.event.set_grab(False)
        self.user = tweet_dict['user']
        self.size = self.scaler(tweet_dict['followers'], [10, 1000], [12, 40]) \
            if 'followers' in tweet_dict and type(tweet_dict['followers']) == int else 12
        self.sentiment = tweet_dict['sentiment']
        self.engagement = tweet_dict['engagement']
        self.weight = self.scaler(self.engagement, [0, 100], [1, 9])
        self.text = tweet_dict['text']
        self.tweet = self.create_text(self.text, self.weight, self.size, self.colorizer(self.sentiment), None)[0]
        self.tweetrect = self.tweet.get_rect(left=self.w, top=randint(0, self.h-40-self.size+5))
        self.speed = [-self.scaler(len(tweet_dict['text']), [10, 140], [1, 8]), 0]

    def kill_tweet(self):
        """ Once the tweet has scrolled off the page, remove it from the list."""
        return True if self.tweetrect.right < 0 else False

    def kill_player(self, ship):
        """ Return true if the tweet's bounding box overlaps the ship."""
        return self.tweetrect.colliderect(ship)

    def update_tweet(self):
        """ Move the tweet across the screen."""
        self.tweetrect = self.tweetrect.move(self.speed)

    def render_tweet(self, screen):
        """ Display the tweet. """
        screen.blit(self.tweet, self.tweetrect)


class TweetListener(StreamListener):
    """
    Open and maintain a persistent connection to the Twitter data stream.
    """
    def __init__(self):
        StreamListener.__init__(self)
        self.latest_tweet = None

    def on_data(self, data):
        """Parse tweets as they arrive and send the pertinent elements to the GameScene class to initiate Tweet."""
        tweet = json.loads(data)
        if 'lang' in tweet and tweet['lang'] == "en":
            if 'retweeted_status' in tweet:
                retweets = tweet['retweeted_status']['retweet_count']
                quotes = tweet['retweeted_status']['quote_count']
                replies = tweet['retweeted_status']['reply_count']
                faves = tweet['retweeted_status']['favorite_count']
                engagement = retweets + quotes + replies + faves
            else:
                engagement = 0
            text = tweet['retweeted_status']['extended_tweet']['full_text'] if 'full_text' in tweet else tweet['text']
            user = tweet['user']['screen_name']
            followers = tweet['user']['followers_count'] if tweet['user']['followers_count'] > 0 else 0
            emo = TextBlob(text)
            tweet_deets = {'text': text, 'engagement': engagement, 'user': user, 'followers': followers,
                           'sentiment': emo.sentiment.polarity}
            self.latest_tweet = tweet_deets
        return True

    def on_error(self, status):
        """If the keyword triggers rate-limiting, tell GameScene to stop the game and close listener."""
        if status == 420:
            self.latest_tweet = False
            return False


# RUN THE GAME
try:
    play = GameBase()
    # Play variables are width, height, FPS, and starting scene
    play.run_game(1024, 768, 60, TitleScene)
except Exception as e:
    # traceback.print_exc(file=sys.stdout)
    print(e)
