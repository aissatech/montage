
import datetime

from clastic import redirect
from clastic.errors import BadRequest
from mwoauth import Handshaker, RequestToken

from mw import public
from rdb import User

from utils import load_env_config

config = load_env_config()
DEBUG = config.get('debug', False)

WIKI_OAUTH_URL = "https://meta.wikimedia.org/w/index.php"


def get_public_routes():
    ret = [('/', home),
           ('/login', login),
           ('/logout', logout),
           ('/complete_login', complete_login),
           ('/series/<series_id?int>', get_series),
           ('/series', get_series)]
    return ret


@public
def home(cookie, request):
    headers = dict([(k, v) for k, v in
                    request.environ.items() if k.startswith('HTTP_')])
    return {'cookie': dict(cookie),
            'headers': headers}


@public
def login(request, consumer_token, cookie, root_path):
    handshaker = Handshaker(WIKI_OAUTH_URL, consumer_token)

    redirect_url, request_token = handshaker.initiate()

    cookie['request_token_key'] = request_token.key
    cookie['request_token_secret'] = request_token.secret

    cookie['return_to_url'] = request.args.get('next', root_path)
    return redirect(redirect_url)


@public
def logout(request, cookie, root_path):
    cookie.pop('userid', None)
    cookie.pop('username', None)

    return_to_url = request.args.get('next', root_path)

    return redirect(return_to_url)


@public
def complete_login(request, consumer_token, cookie, rdb_session, root_path):
    # TODO: Remove or standardize the DEBUG option
    if DEBUG:
        identity = {'sub': 6024474,
                    'username': 'Slaporte'}
    else:
        handshaker = Handshaker(WIKI_OAUTH_URL, consumer_token)

        try:
            rt_key = cookie['request_token_key']
            rt_secret = cookie['request_token_secret']
        except KeyError:
            # in some rare cases, stale cookies are left behind
            # and users have to click login again
            # TODO: clear cookie and redirect home instead
            # redirect(root_path)
            return BadRequest('Invalid cookie. Try clearing your cookies'
                              ' and logging in again.')

        req_token = RequestToken(rt_key, rt_secret)

        access_token = handshaker.complete(req_token,
                                           request.query_string)
        identity = handshaker.identify(access_token)

    userid = identity['sub']
    username = identity['username']
    user = rdb_session.query(User).filter(User.id == userid).first()
    now = datetime.datetime.utcnow()
    if user is None:
        user = User(id=userid, username=username, last_active_date=now)
        rdb_session.add(user)
    else:
        user.last_active_date = now

    # These would be useful when we have oauth beyond simple ID, but
    # they should be stored in the database along with expiration times.
    # ID tokens only last 100 seconds or so
    # cookie['access_token_key'] = access_token.key
    # cookie['access_token_secret'] = access_token.secret

    # identity['confirmed_email'] = True/False might be interesting
    # for contactability through the username. Might want to assert
    # that it is True.

    cookie['userid'] = identity['sub']
    cookie['username'] = identity['username']

    return_to_url = cookie.get('return_to_url')
    # TODO: Clean up
    if not DEBUG:
        del cookie['request_token_key']
        del cookie['request_token_secret']
        del cookie['return_to_url']
    else:
        return_to_url = '/'
    return redirect(return_to_url)

@public
def get_series(user_dao, series_id=None):
    if series_id:
        series = user_dao.get_series(series_id)
    else:
        series = user_dao.get_all_series()
    return {'data': [s.to_details_dict() for s in series]}


PUBLIC_ROUTES = get_public_routes()
