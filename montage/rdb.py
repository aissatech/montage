# Relational database models for Montage
import json
import random
import itertools
from math import ceil

from sqlalchemy import (Column,
                        String,
                        Integer,
                        Float,
                        Boolean,
                        DateTime,
                        ForeignKey)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.associationproxy import association_proxy

from simple_serdes import DictableBase, JSONEncodedDict


Base = declarative_base(cls=DictableBase)


# Some basic display settings for now
DEFAULT_ROUND_CONFIG = json.dumps({'show_link': True,
                                   'show_filename': True,
                                   'show_resolution': True})

"""
Column ordering and groupings:
* ID
* Data
* Metadata (creation date)
* 1-n relationships
* n-n relationships
"""


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String)
    flags = Column(JSONEncodedDict)
    last_login_date = Column(DateTime)

    create_date = Column(DateTime, server_default=func.now())

    coordinated_campaigns = relationship('CampaignCoord', back_populates='user')
    campaigns = association_proxy('coordinated_campaigns', 'campaign',
                                  creator=lambda c: CampaignCoord(campaign=c))

    jurored_rounds = relationship('RoundJuror', back_populates='user')
    rounds = association_proxy('jurored_rounds', 'round',
                               creator=lambda r: RoundJuror(round=r))
    # update_date?

    def __init__(self, **kw):
        self.flags = kw.pop('flags', {})
        super(User, self).__init__(**kw)


class Campaign(Base):
    __tablename__ = 'campaigns'

    id = Column(Integer, primary_key=True)
    name = Column(String)

    # open/close can be used to select/verify that images were
    # actually uploaded during the contest window
    open_date = Column(DateTime)
    close_date = Column(DateTime)

    create_date = Column(DateTime, server_default=func.now())

    rounds = relationship('Round', back_populates='campaign')
    campaign_coords = relationship('CampaignCoord')
    coords = association_proxy('campaign_coords', 'user',
                               creator=lambda user: CampaignCoord(coord=user))
    # round_names = association_proxy('rounds', 'name') "simplifying scalar stuff"


class CampaignCoord(Base):  # Coordinator, not Coordinate
    __tablename__ = 'campaign_coords'

    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True)
    campaign_id = Column(Integer, ForeignKey('campaigns.id'), primary_key=True)

    user = relationship('User', back_populates='coordinated_campaigns')
    campaign = relationship('Campaign', back_populates='campaign_coords')

    def __init__(self, campaign=None, coord=None):
        if campaign is not None:
            self.campaign = campaign
        self.user = coord


class Round(Base):
    """The "directions" field is for coordinators to communicate
    localized directions to jurors, whereas the "description" field is
    for coordinator comments (and not shown to jurors).
    """
    __tablename__ = 'rounds'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(String)
    directions = Column(String)
    open_date = Column(DateTime)
    close_date = Column(DateTime)
    status = Column(String)
    vote_method = Column(String)
    quorum = Column(Integer)
    # Should we just have some settings in json? yes. -mh
    config_json = Column(String, default=DEFAULT_ROUND_CONFIG)

    create_date = Column(DateTime, server_default=func.now())

    campaign_id = Column(Integer, ForeignKey('campaigns.id'))
    # increments for higher rounds within the same campaign
    campaign_seq = Column(Integer, default=1)
    campaign = relationship('Campaign', back_populates='rounds')

    round_jurors = relationship('RoundJuror')
    jurors = association_proxy('round_jurors', 'user',
                               creator=lambda u: RoundJuror(user=u))

    round_entries = relationship('RoundEntry')
    entries = association_proxy('round_entries', 'entry',
                                creator=lambda e: RoundEntry(entry=e))


class RoundJuror(Base):
    __tablename__ = 'round_jurors'

    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True)
    round_id = Column(Integer, ForeignKey('rounds.id'), primary_key=True)
    is_active = Column(Boolean, default=True)

    user = relationship('User', back_populates='jurored_rounds')
    round = relationship('Round', back_populates='round_jurors')

    def __init__(self, round=None, user=None):
        if round is not None:
            # lesson: setting round to None would give an error about
            # trying to "blank-out primary key column"
            self.round = round
        if user is not None:
            self.user = user


class Entry(Base):
    # if this is being kept generic for other types of media judging,
    # then I think a "duration" attribute makes sense -mh
    __tablename__ = 'entries'

    id = Column(Integer, primary_key=True)

    # page_id?
    name = Column(String)
    mime_major = Column(String)
    mime_minor = Column(String)
    width = Column(Integer)
    height = Column(Integer)
    resolution = Column(Integer)
    # if we ever figure out how to get the monument ID
    subject_id = Column(String)
    upload_user_id = Column(Integer)
    upload_user_text = Column(String)
    upload_date = Column(DateTime)

    # TODO: img_sha1/page_touched for updates?
    create_date = Column(DateTime, server_default=func.now())

    entered_rounds = relationship('RoundEntry')
    rounds = association_proxy('entered_rounds', 'round',
                               creator=lambda r: RoundEntry(round=r))


class RoundEntry(Base):
    __tablename__ = 'round_entries'

    id = Column(Integer, primary_key=True)
    entry_id = Column(Integer, ForeignKey('entries.id'))
    round_id = Column(Integer, ForeignKey('rounds.id'))

    dq_reason = Column(String)  # in case it's disqualified
    # examples: too low resolution, out of date range

    entry = relationship(Entry, back_populates='entered_rounds')
    round = relationship(Round, back_populates='round_entries')

    def __init__(self, entry=None, round=None):
        if entry is not None:
            self.entry = entry
        if round is not None:
            self.round = round
        return


class Rating(Base):
    __tablename__ = 'votes'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    entry_id = Column(Integer, ForeignKey('entries.id'))
    round_id = Column(Integer, ForeignKey('rounds.id'))
    task_id = Column(Integer, ForeignKey('tasks.id'))

    value = Column(Float)

    create_date = Column(DateTime, server_default=func.now())


class Ranking(Base):
    __tablename__ = 'rankings'

    id = Column(Integer, primary_key=True)
    # user_id = Column(Integer, ForeignKey('users.id'))


class Task(Base):
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    round_entry_id = Column(Integer, ForeignKey('round_entries.id'))

    user = relationship('User')
    round_entry = relationship('RoundEntry')

    create_date = Column(DateTime, server_default=func.now())
    complete_date = Column(DateTime)
    cancel_date = Column(DateTime)


class UserDAO(object):
    """The Data Acccess Object wraps the rdb_session and active user
    model, providing a layer for model manipulation through
    expressively-named methods.

    As the DAO expands, it will likely break up into multiple DAOs for
    different areas of the schema.

    # TODO: name? true that user is bound in, but UserDAO doesn't ring
    totally true. ActorDAO?
    # TODO: will blow up a bit if user is None

    # TODO: rather than query(Model), this should do user.models and
    filter from there, I'm thinking.
    """
    def __init__(self, rdb_session, user):
        self.rdb_session = rdb_session
        self.user = user

    def query(self, *a, **kw):
        "a call-through to the underlying session.query"
        return self.rdb_session.query(*a, **kw)

    def get_campaign_config(self, campaign_id=None):
        campaign = self.query(Campaign)\
                       .filter(
                           Campaign.coords.any(username=self.user.username))\
                       .filter_by(id=campaign_id)\
                       .one()
        return campaign

    def get_campaign(self, campaign_id):
        campaign = self.query(Campaign)\
                       .filter(Campaign.rounds.any(
                           Round.jurors.any(username=self.user.username)))\
                       .filter_by(id=campaign_id)\
                       .one()
        rounds = self.query(Round)\
                     .filter(Round.jurors.any(username=self.user.username),
                             Round.campaign_id == campaign_id)\
                     .all()
        ret = campaign.to_dict()
        ret['rounds'] = [r.to_dict() for r in rounds]
        return ret

    def get_campaign_name(self, campaign_id):
        # TODO: check user permissions?
        campaign = self.query(Campaign).filter_by(id=campaign_id).one()
        return campaign.name

    def get_round_name(self, round_id):
        # TODO: check user permissions?
        round = self.query(Round).filter_by(id=round_id).one()
        return round.name

    def get_round_config(self, round_id):
        round = self.query(Round)\
                    .filter(
                        Round.campaign.has(
                            Campaign.coords.any(username=self.user.username)),
                        Round.id == round_id)\
                    .one()
        return round

    def get_round(self, round_id):
        round = self.query(Round)\
                    .filter(
                        Round.jurors.any(username=self.user.username),
                        Round.id == round_id)\
                    .one()
        return round

    def get_all_campaigns(self):
        campaigns = self.query(Campaign)\
                        .filter(
                            Campaign.coords.any(username=self.user.username))\
                        .all()
        return campaigns

    def get_all_rounds(self):
        rounds = self.query(Round)\
                     .filter(Round.jurors.any(username=self.user.username))\
                     .group_by(Round.campaign_id)\
                     .all()
        ret = [r.to_dict() for r in rounds]
        return ret


def create_initial_tasks(rdb_session, round):
    """this creates the initial tasks.

    there may well be a separate function for reassignment which reads
    from the incomplete Tasks table (that will have to ensure not to
    assign a rating which has already been completed by the same
    juror)
    """
    # TODO: deny quorum > number of jurors
    ret = []

    quorum = round.quorum
    jurors = [rj.user for rj in round.round_jurors if rj.is_active]
    random.shuffle(jurors)

    rdb_type = rdb_session.bind.dialect.name

    if rdb_type == 'mysql':
        rand_func = func.rand()
    else:
        rand_func = func.random()

    # this does the shuffling in the database
    shuffled_entries = rdb_session.query(RoundEntry)\
                                  .filter(RoundEntry.round_id == round.id)\
                                  .order_by(rand_func).all()

    to_process = itertools.chain.from_iterable([shuffled_entries] * quorum)
    # some pictures may get more than quorum votes
    # it's either that or some get less
    per_juror = int(ceil(len(shuffled_entries) * (float(quorum) / len(jurors))))

    juror_iters = itertools.chain.from_iterable([itertools.repeat(j, per_juror)
                                                 for j in jurors])

    pairs = itertools.izip_longest(to_process, juror_iters, fillvalue=None)
    for entry, juror in pairs:
        if juror is None:
            raise RuntimeError('should never run out of jurors first')
        if entry is None:
            break

        # TODO: bulk_save_objects
        task = Task(user=juror, round_entry=entry)
        ret.append(task)

    return ret


"""* Indexes
* db session management, engine creation, and schema creation separation
* prod db pw management
* add simple_serdes for E-Z APIs

TODO: what should the tallying for ratings look like? Get all the
ratings that form the quorum and average them? or median? (sum is the
same as average) what about when images have more than quorum ratings?

"""
