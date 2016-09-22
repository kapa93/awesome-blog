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
from main import *
from google.appengine.ext import db

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = True)


class BlogHandler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)

    def render_str(self, template, **params):
        params['user'] = self.user
        return render_str(template, **params)

    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))

    def set_secure_cookie(self, name, val):
        cookie_val = make_secure_val(val)
        self.response.headers.add_header(
            'Set-Cookie',
            '%s=%s; Path=/' % (name, cookie_val))

    def read_secure_cookie(self, name):
        cookie_val = self.request.cookies.get(name)
        return cookie_val and check_secure_val(cookie_val)

    def login(self, user):
        self.set_secure_cookie('user_id', str(user.key().id()))

    def logout(self):
        self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/')

    def initialize(self, *a, **kw):
        webapp2.RequestHandler.initialize(self, *a, **kw)
        uid = self.read_secure_cookie('user_id')
        self.user = uid and User.by_id(int(uid))

    def verify_cookie(self):
        user_id = self.request.cookies.get('user_id')

        if user_id and check_secure_val(user_id):
            return User.by_id(int(user_id.split('|')[0]))

    def verify_post_id(self, post_id):
        key = db.Key.from_path('Post', int(post_id), parent=blog_key())
        return db.get(key)

    def verify_comment_id(self, comment_id, post_id):
        key = db.Key.from_path('Comment', int(comment_id), parent=blog_key())
        comment = db.get(key)
        post = self.verify_post_id(post_id)

        if comment and post and comment.post_id == int(post_id):
            return comment

def render_post(response, post):
    response.out.write('<b>' + post.subject + '</b><br>')
    response.out.write(post.content)

class MainPage(BlogHandler):
  def get(self):
      self.render('signup-form.html')

# Home page that displays the 10 most recent posts. 
class BlogFront(BlogHandler):
    def get(self):
        if self.user:
            posts = db.GqlQuery("SELECT * "
                            "FROM Post "
                            "ORDER BY created DESC LIMIT 10")
            self.render("front.html", posts=posts)
        else:
            self.redirect('/signup')

    def post(self):
        auth_error = True
        if self.read_secure_cookie('user_id'):
            auth_error = False
        else:
            auth_error = True
        username = self.read_secure_cookie('user_id')

        if not auth_error:
            edit_post_id = self.request.get('edit_post_id')
            if edit_post_id:
                post_id = edit_post_id
                self.redirect('/editpost?post_id=' + post_id)
            user_id = self.read_secure_cookie('user_id')
        else:
            self.redirect('/signup')

# Handles posts by linking the post id with the user id.
class PostPage(BlogHandler):
    def get(self, post_id):
        key = db.Key.from_path('Post', int(post_id), parent=blog_key())
        post = db.get(key)

        if not post:
            self.error(404)
            return

        comments = Comment.gql("WHERE post_id=%s" % (post_id))

        self.render("permalink.html", post = post, user=self.user, comments=comments)

    def post(self, post_id):
        auth_error = True
        if self.read_secure_cookie('user_id'):
            auth_error = False
        else:
            auth_error = True
        username = self.read_secure_cookie('user_id')

        if not auth_error:
            edit_post_id = self.request.get('edit_post_id')
            if edit_post_id:
                post_id = edit_post_id
                self.redirect('/editpost?post_id=' + post_id)
        else:
            self.redirect('/signup')

# Allows users to like other people's posts.
class LikePost(BlogHandler):
    def get(self, post_id):
        self.post(post_id)

    def post(self, post_id):
        post = self.verify_post_id(post_id)
        if not self.user:
            return self.redirect('/login')

        if self.read_secure_cookie('user_id'):
            user_id = self.read_secure_cookie('user_id')
            if user_id == post.author_id:
                return self.redirect('/blog')

            likes = db.GqlQuery('SELECT * FROM PostLike WHERE author_id = \'%s\' and post_id = %s' % (user_id, post_id))

            like = likes.get()

            if not like:
                post.likes += 1
                post.put()
                like = PostLike(author_id=user_id,
                                post_id=int(post_id))
                like.put()

            else:
                post.likes -= 1
                post.put()
                db.delete(like.key())

            self.redirect('/blog/%s' % (post_id))

# Allows users to like other people's comments.
class LikeComment(BlogHandler):
    def get(self, post_id, comment_id):
        self.post(post_id, comment_id)

    def post(self, post_id, comment_id):
        post = self.verify_post_id(post_id)
        comment = self.verify_comment_id(comment_id, post_id)

        if not self.user:
            return self.redirect('/login?error=\You+need+to+be+logged+in+to+like!')

        if self.read_secure_cookie('user_id'):
            user_id = self.read_secure_cookie('user_id')
            if user_id == comment.author_id:
                return self.redirect('/blog/%s' % (post_id))

        likes = db.GqlQuery('SELECT * FROM CommentLike WHERE author_id = \'%s\' and comment_id = %s and post_id = %s' % (user_id, comment_id, post_id))

        like = likes.get()

        if not like:
            comment.likes += 1
            comment.put()
            like = CommentLike(author_id=user_id,
                                post_id=int(post_id),
                                comment_id=int(comment_id))
            like.put()

        else:
            comment.likes -= 1
            comment.put()
            db.delete(like.key())

        self.redirect('/blog/%s' % (post_id))

# Allows users to comment on blog posts.
class NewComment(BlogHandler):
    def get(self, post_id):
        if self.user:
            self.render('newcomment.html')
        else:
            self.redirect('/login?error=You+need+to+be+logged+in+to+comment!')

    def post(self, post_id):
        if self.user:
            author_id = self.read_secure_cookie('user_id')
            content = self.request.get('content')
            post_id = int(post_id)
            comment = Comment(author_id=author_id,
                            content=content,
                            post_id=post_id,
                            parent=blog_key())
            comment.put()
            self.redirect('/blog/%s' % (post_id))
        else:
            self.redirect('/login?error=You+need+to+be+logged+in+to+comment!')

# Gets input from newpost form and saves post in the database.
class NewPost(BlogHandler):
    def get(self):
        if self.read_secure_cookie('user_id'):
            self.render("newpost.html")
        else:
            self.redirect("/login")

    def post(self):
        auth_error = True
        if self.read_secure_cookie('user_id'):
            auth_error = False
        else:
            auth_error = True

        if not auth_error:
            subject = self.request.get('subject')
            content = self.request.get('content')
        if self.read_secure_cookie('user_id'):
            user_id = self.read_secure_cookie('user_id')
            key = db.Key.from_path('User', int(user_id))
            user = db.get(key)

        if subject and content and user_id:
            p = Post(parent = blog_key(),
                    subject = subject,
                    content = content,
                    author_id = user_id)
            p.put()
            post_id = str(p.key().id())
            self.redirect('/blog/%s' % post_id)
        else:
            error = "subject and content, please!"
            self.render("newpost.html", subject=subject, content=content, error=error)

# Allows for editing of post if user is the author.
class EditPost(BlogHandler):
    def get(self):
        """ get request newpost.html """
        post_id = self.request.get('post_id')
        key = db.Key.from_path('Post',
                                int(post_id),
                                parent=blog_key())
        post = db.get(key)
        if self.read_secure_cookie('user_id'):
            user_id = self.read_secure_cookie('user_id')
            # if current user if not the author
            # they get redirected
            if user_id == post.author_id:
                self.render("editpost.html",
                            subject=post.subject,
                            content=post.content,
                            post_id=post_id)
            else:
                self.redirect('/blog/?')
        else:
            self.redirect('/signup')

    def post(self):
        """
        handles POST request from newpost.html
        """
        auth_error = True
        if self.read_secure_cookie('user_id'):
            auth_error = False
        else:
            auth_error = True
        username = self.read_secure_cookie('user_id')

        if not auth_error:
            post_id = self.request.get('post_id')
            subject = self.request.get('subject')
            content = self.request.get('content')
            post_key = db.Key.from_path('Post',
                                        int(post_id),
                                        parent=blog_key())
            if subject and content:
                post = db.get(post_key)
                post.subject = subject
                post.content = content
                post.put()
                # redirect to single post with the post id in the url
                post_id = str(post.key().id())
                self.redirect('/blog/%s' % post_id)
            else:
                error = "subject and content, please!"
                self.render("editpost.html",
                            subject=subject,
                            content=content,
                            error=error,
                            post_id=post_id)
        else:
            self.redirect('/signup')

# Allows for editing of comment if user is the author.
class EditComment(BlogHandler):
    def get(self, post_id, comment_id):
        if self.read_secure_cookie('user_id'):
            user_id = self.read_secure_cookie('user_id')
        comment = self.verify_comment_id(comment_id, post_id)

        if not comment:
            self.error(404)
            return

        if not self.user or user_id != comment.author_id:
            self.redirect(('/login?error=\You+don\'t+have+permission+to+edit+that!'))

        else:
            self.render('newcomment.html',
                        content=comment.content,
                        editcomment=True)

    def post(self, post_id, comment_id):
        if self.read_secure_cookie('user_id'):
            user_id = self.read_secure_cookie('user_id')
        comment = self.verify_comment_id(comment_id, post_id)

        if not comment:
            self.error(404)
            return

        if not self.user or user_id != comment.author_id:
            self.redirect('/login?error=\You+don\'t+have+permission+to+edit+that!')

        else:
            content = self.request.get('content')

            if content:
                comment.content = content
                comment.put()
                self.redirect('/blog/%s' % (post_id))

            else:
                error = "Include some content!"
                self.render('newcomment.html',
                            content=content,
                            error=error,
                            editcomment=True)

#Deletes post after checking if the user is the author of the post.
class DeletePost(BlogHandler):
    def post(self):
        if self.read_secure_cookie('user_id'):
            user_id = self.read_secure_cookie('user_id')
            post_id = self.request.get('post_id')
            key = db.Key.from_path('Post',
                                int(post_id),
                                parent=blog_key())
            post = db.get(key)

            if user_id == post.author_id:
                db.delete(key)
                self.render('/postdeleted.html')
            else:
                self.redirect('/blog')

# Deletes comment after checking if user is the author of the comment.
class DeleteComment(BlogHandler):
    def get(self, post_id, comment_id):
        self.post(post_id, comment_id)

    def post(self, post_id, comment_id):
        if self.read_secure_cookie('user_id'):
            user_id = self.read_secure_cookie('user_id')
        comment = self.verify_comment_id(comment_id, post_id)

        if not comment:
            self.error(404)
            return

        if not self.user or user_id != comment.author_id:
            self.redirect('/login?error=\you+don\'t+have+permission+to+delete+that!')

        else:
            db.delete(comment.key())
            self.redirect('/blog/%s' % (post_id)) 

# Handles input from the signup form.
class Signup(BlogHandler):
    def get(self):
        self.render("signup-form.html")

    def post(self):
        have_error = False
        self.username = self.request.get('username')
        self.password = self.request.get('password')
        self.verify = self.request.get('verify')
        self.email = self.request.get('email')

        params = dict(username = self.username,
                      email = self.email)

        if not valid_username(self.username):
            params['error_username'] = "That's not a valid username."
            have_error = True

        if not valid_password(self.password):
            params['error_password'] = "That wasn't a valid password."
            have_error = True
        elif self.password != self.verify:
            params['error_verify'] = "Your passwords didn't match."
            have_error = True

        if not valid_email(self.email):
            params['error_email'] = "That's not a valid email."
            have_error = True

        if have_error:
            self.render('signup-form.html', **params)
        else:
            self.done()

    def done(self, *a, **kw):
        raise NotImplementedError

# Registers new users in the database.
class Register(Signup):
    def done(self):
        #make sure the user doesn't already exist
        u = User.by_name(self.username)
        if u:
            msg = 'That user already exists.'
            self.render('signup-form.html', error_username = msg)
        else:
            u = User.register(self.username, self.password, self.email)
            u.put()

            self.login(u)
            self.redirect('/blog')

# Checks if username and password exist in database.
class Login(BlogHandler):
    def get(self):
        self.render('login-form.html')

    def post(self):
        username = self.request.get('username')
        password = self.request.get('password')

        u = User.login(username, password)
        if u:
            self.login(u)
            self.redirect('/blog')
        else:
            msg = 'Invalid login'
            self.render('login-form.html', error = msg)

class Logout(BlogHandler):
    def get(self):
        self.logout()
        self.redirect('/blog')