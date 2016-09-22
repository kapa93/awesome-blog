import os
import re
import random
import hashlib
import hmac
from string import letters
import webapp2
import jinja2

from user import *
from blog import *
from handlers import *

from google.appengine.ext import db

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = True)


app = webapp2.WSGIApplication([('/', MainPage),
                               ('/blog/?', BlogFront),
                               ('/blog/([0-9]+)', PostPage),
                               ('/blog/newpost', NewPost),
                               ('/signup', Register),
                               ('/editpost', EditPost),
                               ('/blog/([0-9]+)/([0-9]+)/edit', EditComment),
                               ('/deletepost', DeletePost),
                               ('/blog/([0-9]+)/([0-9]+)/delete', DeleteComment),
                               ('/blog/([0-9]+)/like', LikePost),
                               ('/blog/([0-9]+)/([0-9]+)/like', LikeComment),
                               ('/blog/([0-9]+)/comment', NewComment),
                               ('/login', Login),
                               ('/logout', Logout),
                               ],
                              debug=True)

