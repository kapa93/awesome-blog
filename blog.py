import os
import re
import random
import hashlib
import hmac
from string import letters
import webapp2
import jinja2

from user import *
from google.appengine.ext import db

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = True)

# Defines blog key
def blog_key(name = 'default'):
    return db.Key.from_path('blogs', name)

def post_key(post_id):
    return db.Key.from_path('Post', int(post_id), parent=blog_key())

# Database model for posts.
class Post(db.Model):
    subject = db.StringProperty(required = True)
    content = db.TextProperty(required = True)
    created = db.DateTimeProperty(auto_now_add = True)
    last_modified = db.DateTimeProperty(auto_now = True)
    author_id = db.StringProperty()
    likes = db.IntegerProperty(default=0)

    def render(self, post_id):
        self._render_text = self.content.replace('\n', '<br>')
        return render_str("post.html", p = self)

# Database model for comments.
class Comment(db.Model):
    author_id = db.StringProperty(required=True)
    content = db.StringProperty(required=True)
    post_id = db.IntegerProperty(required=True)
    created = db.DateTimeProperty(auto_now_add=True)
    last_modified = db.DateTimeProperty(auto_now=True)
    likes = db.IntegerProperty(default=0)

    def render(self, **kw):
        kw['comment'] = self
        self._render_text = self.content.replace('\n', '<br>')
        return render_str("comment.html", **kw)

# Database model for post likes.
class PostLike(db.Model):
    author_id = db.StringProperty()
    post_id = db.IntegerProperty()

# Database model for comment likes.
class CommentLike(db.Model):
    author_id = db.StringProperty(required=True)
    post_id = db.IntegerProperty(required=True)
    comment_id = db.IntegerProperty(required=True)

