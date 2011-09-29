from datetime import datetime
import os
import re
import time

from sqlalchemy import create_engine, desc
from sqlalchemy import Column, Integer, String, Enum, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, backref
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.schema import UniqueConstraint

import tornado.ioloop
import tornado.web


##########
# Helpers
#
def sanitize_name(name):
    return re.sub(r"[^a-zA-Z0-9]", "", name)
    

def get_app_abs_path(path):
    return os.path.join(os.path.dirname(__file__), path)
    
    
def get_store():
    return Store(settings["database"])
    
    
##########
# Mapping
#
BaseModel = declarative_base()


class User(BaseModel):

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String)
    teamname = Column(String)
    
    __table_args__ = (
        UniqueConstraint('username'),
    )
    
        
class Code(BaseModel):

    __tablename__ = "codes"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    timestamp = Column(DateTime)
    tags = Column(String)
    lines = Column(Integer)
    status = Column(Enum("new", "printing", "delivered"))
    code = Column(String)
    
    user = relationship("User", backref=backref("codes", order_by=id))
    

##########
# Handlers
#
class BaseHandler(tornado.web.RequestHandler):

    __session = None

    def get_current_user(self):
        session = self.get_session()
        username = self.get_secure_cookie("username")
        try:
            user = session.query(User).filter_by(username=username).one()
            return user
        except NoResultFound:
            return None
            
    def get_session(self):
        if self.__session is None:
            self.__session = Session()
        return self.__session
        

class MainHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render("main.html")

        
class LoginHandler(BaseHandler):

    def get(self):
        self.render("login.html", errors=[])

    def post(self):
        session = self.get_session()
        teamname = self.get_argument("teamname", "")
        username = sanitize_name(teamname)
        if len(username) < 3:
            self.render("login.html", errors=["Nome de time muito curto."])
            return
        try:
            user = session.query(User).filter_by(username=username).one()
        except NoResultFound:
            user = User()
            user.username = username
            user.teamname = teamname
            session.add(user)
            session.commit()
        self.set_secure_cookie("username", user.username)
        if username == settings["super_secret"]:
            self.redirect("/super")
        else:
            self.redirect("/")
        
        
class LogoutHandler(BaseHandler):
    def get(self):
        self.set_secure_cookie("username", "")
        self.redirect("/")
        
        
class SubmitHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        session = self.get_session()
        code = Code()
        code.user = self.current_user
        code.timestamp = datetime.now()
        code.code = self.get_argument("code")
        code.tags = self.get_argument("tags", "")
        code.lines = code.code.count("\n") + 1
        code.status = "new"
        session.add(code)
        session.commit()
        Notifier.notify()
        
        
class UpdateHandler(BaseHandler):

    @tornado.web.authenticated
    @tornado.web.asynchronous
    def get(self):
        cursor = int(self.get_argument("cursor", -1))
        Notifier.add_callback(self.callback, cursor)
    
    def callback(self, cursor):
        if self.request.connection.stream.closed():
            return
        self.finish({"cursor": cursor})


class SubmissionsHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self):
        session = self.get_session()
        self.render(
            "submissions.html",
            submissions=session.query(Code)\
                               .filter_by(user_id=self.current_user.id)\
                               .order_by(desc(Code.id))\
                               .all()
        )
        
        
class SeeHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self, id):
        session = self.get_session()
        code = session.query(Code)\
                      .filter_by(id=id)\
                      .filter_by(user_id=self.current_user.id)\
                      .scalar()
        if code is None:
            raise tornado.web.HTTPError(404)
        self.set_header("Content-Type", "text/plain")
        self.write(code.code)
        

class SuperBaseHandler(BaseHandler):

    def check_super(self):
        if self.current_user.username != settings["super_secret"]:
            raise tornado.web.HTTPError(404)
        
        
class SuperMainHandler(SuperBaseHandler):
    
    @tornado.web.authenticated
    def get(self):
        self.check_super()
        self.render("super_main.html")
        
        
class SuperSubmissionsHandler(SuperBaseHandler):

    @tornado.web.authenticated
    def get(self):
        self.check_super()
        session = self.get_session()
        self.render(
            "super_submissions.html",
            submissions=session.query(Code)\
                               .order_by(desc(Code.id))\
                               .all()
        )
                    
        
class SuperSeeHandler(SuperBaseHandler):

    @tornado.web.authenticated
    def get(self, id):
        self.check_super()
        session = self.get_session()
        code = session.query(Code)\
                      .filter_by(id=id)\
                      .scalar()
        if code is None:
            raise tornado.web.HTTPError(404)
        self.render("super_see.html", code=code)
        
        
class SuperActionHandler(SuperBaseHandler):

    @tornado.web.authenticated
    def get(self, id, action):
        self.check_super()
        session = self.get_session()
        code = session.query(Code).filter_by(id=id).one()
        if action == "delete":
            session.delete(code)
        else:
            code.status = action
        session.commit()
        Notifier.notify()
        
        
class SuperNotifyHandler(SuperBaseHandler):

    @tornado.web.authenticated
    def get(self):
        self.check_super()
        Notifier.notify()
        

##########
# Notifier
#
class Notifier(object):

    __cursor = 10
    __callbacks = []
    
    @classmethod
    def add_callback(cls, callback, cursor):
        if cursor < cls.__cursor:
            callback(cls.__cursor)
        else:
            cls.__callbacks.append(callback)
            
    @classmethod
    def notify(cls):
        cls.__cursor += 1
        for callback in cls.__callbacks:
            callback(cls.__cursor)
        cls.__callbacks = []
        

##########
# Main/Settings
#       
settings = {
    "static_path": get_app_abs_path("static"),
    "template_path": get_app_abs_path("tmpl"),
    "cookie_secret": "S39Un0HjQLmR7LRMzdg0WDavKI3VkkGJoPlCGMO0tOQ=",
    "super_secret": "sHCxUCh7MH28HBTxBcSftQCNMlVBy894zUztTOPn1kCnHAbDD2",
    "login_url": "/login",
    "debug": True,
}

application = tornado.web.Application([
    (r"/", MainHandler),
    (r"/login", LoginHandler),
    (r"/logout", LogoutHandler),
    (r"/submit", SubmitHandler),
    (r"/update", UpdateHandler),
    (r"/submissions", SubmissionsHandler),
    (r"/see/([0-9]+)", SeeHandler),
    (r"/super", SuperMainHandler),
    (r"/super/submissions", SuperSubmissionsHandler),
    (r"/super/see/([0-9]+)", SuperSeeHandler),
    (r"/super/set/([0-9]+)/([a-z]+)", SuperActionHandler),
    (r"/super/notify", SuperNotifyHandler),
], **settings)

engine = create_engine("sqlite:///" + get_app_abs_path("var/db.db"))

# BaseModel.metadata.drop_all(engine)
BaseModel.metadata.create_all(engine)
    
Session = sessionmaker(bind=engine)

if __name__ == "__main__":
    application.listen(80)
    tornado.ioloop.IOLoop.instance().start()
