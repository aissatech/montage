"""x Logging in
 - Health check
 - Coordinators
  x See a list of campaigns
  - Save edits to a campaign
  x See a list of rounds per campaign
  - Save edits to a round
  - Import photos for a round
  - Close out a round
  - Export the output from a round
  - Send notifications to coordinators & jurors (?)
 - Jurors
  x See a list of campaigns and rounds
  - See the next vote
  - Submit a vote
  - Skip a vote
  - Expoert their own votes (?)
  - Change a vote for an open round (?)

Practical design:

Because we're building on angular, most URLs return JSON, except for
login and complete_login, which give back redirects, and the root
page, which gives back the HTML basis.

# A bit of TBI design

We add privileged Users (with coordinator flag enabled). Coordinators
can create Campaigns, and see and interact only with Campaigns they've
created or been added to. Can Coordinators create other Coordinators?

"""
import sys
import os.path
import datetime

import yaml

from clastic import Application, redirect, GET, POST
from clastic.errors import Forbidden
from clastic.static import StaticApplication
from clastic.middleware.cookie import SignedCookieMiddleware, NEVER
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from boltons.strutils import slugify
from mwoauth import ConsumerToken, Handshaker, RequestToken

from mw import (public,
                UserMiddleware,
                MessageMiddleware,
                DBSessionMiddleware)
from rdb import Base, User, Campaign
from rdb_check import get_schema_errors


WIKI_OAUTH_URL = "https://meta.wikimedia.org/w/index.php"
DEFAULT_DB_URL = 'sqlite:///tmp_montage.db'
CUR_PATH = os.path.dirname(os.path.abspath(__file__))
STATIC_PATH = os.path.join(CUR_PATH, 'static')

ROOT_ADMINS = ['MahmoudHashemi', 'Slaporte', 'Yarl']


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
def complete_login(request, consumer_token, cookie, rdb_session):
    handshaker = Handshaker(WIKI_OAUTH_URL, consumer_token)

    req_token = RequestToken(cookie['request_token_key'],
                             cookie['request_token_secret'])

    access_token = handshaker.complete(req_token,
                                       request.query_string)
    identity = handshaker.identify(access_token)

    userid = identity['sub']
    username = identity['username']
    user = rdb_session.query(User).filter(User.id == userid).first()
    now = datetime.datetime.utcnow()
    if user is None:
        user = User(id=userid, username=username, last_login_date=now)
        rdb_session.add(user)
    else:
        user.last_login_date = now

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
    del cookie['request_token_key']
    del cookie['request_token_secret']
    del cookie['return_to_url']
    return redirect(return_to_url)


#
#  End public/auth endpoint functions
#


def create_campaign(user, rdb_session, request_dict):
    if user.username not in ROOT_ADMINS:
        raise Forbidden('only a root admin can create a campaign')  # for now
    camp = Campaign(name=request_dict['name'])
    rdb_session.add(camp)
    rdb_session.commit()
    return {'data': camp.to_dict()}


def get_admin_landing(user_dao):
    campaigns = user_dao.get_all_campaigns()
    data = []
    for campaign in campaigns:
        camp = get_admin_campaign(user_dao, campaign.id)
        data.append(camp)
    return {'data': data}


def get_admin_campaign(user_dao, campaign_id):
    campaign = user_dao.get_campaign_config(campaign_id)
    info = {'id': campaign.id,
            'name': campaign.name,
            'rounds': [],
            'coords': [u.username for u in campaign.coords]}
    for round in campaign.rounds:
        info['rounds'].append(get_admin_round(user_dao, round.id))

    info['canonical_url_name'] = slugify(info['name'], '-')

    return info


def get_admin_round(user_dao, round_id):
    round = user_dao.get_round_config(round_id)
    # entries_info = user_dao.get_entry_info(round_id) # TODO

    # TODO: joinedload if this generates too many queries
    jurors = [{'username': rj.user.username,
               'id': rj.user.id,
               'active': rj.is_active} for rj in round.round_jurors]

    info = {'id': round.id,
            'name': round.name,
            'voteMethod': round.vote_method,
            'status': round.status,
            'jurors': jurors,
            'quorum': round.quorum,
            'sourceInfo': {
                'entryCount': None,
                'uploadersCount': None,
                'roundSource': {'id': None,
                                'title': None}},
            'closeDate': round.close_date,
            'campaign': round.campaign_id}

    info['canonical_url_name'] = slugify(info['name'], '-')

    return info


# - cancel round
# - update round
#   - no reassignment required: name, description, directions, display_settings
#   - reassignment required: quorum, active_jurors
#   - not updateable: id, open_date, close_date, vote_method, campaign_id/seq



#
#  End admin endpoint functions
#


def get_juror_rounds(user_dao):
    rounds = user_dao.get_all_rounds()
    return {'rounds': rounds}


def get_juror_campaign(user_dao, campaign_id, camp_name):
    campaign = user_dao.get_campaign(campaign_id)
    return {'campaign': campaign}


def get_juror_round(user_dao, round_id):
    # in a SPA, this redirecting/URL correcting behavior is done by the client.
    # correct_name = user_dao.get_round_name(round_id)
    # if round_name != correct_name.replace(' ', '-'):
    #     return juror_round_redirect(user_dao, round_id, correct_name)
    round = user_dao.get_round(round_id)
    return {'round': round.to_dict()}


#
#  End juror endpoint functions
#


def create_app(env_name='prod'):
    # render functions have been removed, as this is now managed by
    # the MessageMiddleware
    routes = [('/', home),
              ('/admin', get_admin_landing),
              GET('/admin/campaign', get_admin_landing),
              POST('/admin/campaign', create_campaign),
              ('/admin/campaign/<campaign_id:int>/<camp_name?>', get_admin_campaign),
              ('/admin/round', get_admin_landing),
              ('/admin/round/<round_id:int>/<round_name?>', get_admin_round),
              ('/campaign', get_juror_rounds),  # TODO
              ('/campaign/<campaign_id:int>/<camp_name?>', get_juror_campaign),
              ('/round', get_juror_rounds),
              ('/round/<round_id:int>/<round_name?>', get_juror_round),
              ('/login', login),
              ('/logout', logout),
              ('/complete_login', complete_login)]

    config_file_name = 'config.%s.yaml' % env_name
    config = yaml.load(open(config_file_name))

    engine = create_engine(config.get('db_url', DEFAULT_DB_URL))
    session_type = sessionmaker()
    session_type.configure(bind=engine)

    # import pdb;pdb.set_trace()

    tmp_rdb_session = session_type()
    schema_errors = get_schema_errors(Base, tmp_rdb_session)
    if not schema_errors:
        print '++  schema validated ok'
    else:
        for err in schema_errors:
            print '!! ', err
        print '!!  recreate the database and update the code, then try again'
        sys.exit(2)

    engine.echo = config.get('db_echo', False)

    cookie_secret = config['cookie_secret']
    assert cookie_secret

    root_path = config.get('root_path', '/')

    scm_secure = env_name == 'prod'  # https only in prod
    scm_mw = SignedCookieMiddleware(secret_key=cookie_secret,
                                    path=root_path,
                                    http_only=True,
                                    secure=scm_secure)
    if not scm_secure:
        scm_mw.data_expiry = NEVER

    middlewares = [MessageMiddleware(),
                   scm_mw,
                   DBSessionMiddleware(session_type),
                   UserMiddleware()]

    consumer_token = ConsumerToken(config['oauth_consumer_token'],
                                   config['oauth_secret_token'])

    resources = {'config': config,
                 'consumer_token': consumer_token,
                 'root_path': root_path}

    app = Application(routes, resources, middlewares=middlewares)

    static_app = StaticApplication(STATIC_PATH)

    root_app = Application([('/', app),
                            ('/static/', static_app)])

    return root_app


if __name__ != '__main__':
    # generally imported for serving, ideally this would be side-effect free
    app = create_app(env_name="prod")
else:
    app = create_app(env_name="dev")
    app.serve()
