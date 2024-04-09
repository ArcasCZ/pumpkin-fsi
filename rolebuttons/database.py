from __future__ import annotations

import enum
from typing import List, Optional

import discord
from sqlalchemy import BigInteger, Boolean, Column, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from pie.database import database, session


class DiscordType(enum.Enum):
    ROLE = 0
    CHANNEL = 1


class RestrictionType(enum.Enum):
    ALLOW = 0
    DISALLOW = 1


class RBMessage(database.base):
    """Holds list of messages with assigned RBView.
    It should be mainly used to update messages on RBView edit
    and also for removing views when RBView is deleted.

    Attributes:
        message_id: ID of message
        channel_id: ID of message's channel
        view_id: ID of parent RB View
    """

    __tablename__ = "fsi_rolebutton_message"

    message_id = Column(BigInteger, primary_key=True)
    channel_id = Column(BigInteger)
    view_id = Column(Integer, ForeignKey("fsi_rolebutton_view.idx"), primary_key=True)
    rbview = relationship(lambda: RBView, back_populates="messages")

    @staticmethod
    def get(message_id: int):
        query = session.query(RBMessage).filter_by(message_id=message_id).one_or_none()
        return query

    def __repr__(self) -> str:
        return (
            f'<RBMessage message_id="{self.message_id}" channel_id="{self.channel_id}" '
            f'view_id="{self.view_id}" rbview="{self.rbview}">'
        )

    def dump(self) -> dict:
        return {
            "message_id": self.message_id,
            "channel_id": self.channel_id,
            "view_id": self.view_id,
            "rbview": self.rbview,
        }


class RBRestriction(database.base):
    """Main purpose of this table is to hold
        roles which are (dis-)allowed to use specific
        RBView. Type of restriction is determined
        by :class:`RestrictionType`.
    .
        Attributes:
            view_id: ID of parent RB View
            role_id: ID of assigned role
            type: Restriction type defined in :class:`RestrictionType`
    """

    __tablename__ = "fsi_rolebutton_restriction"

    view_id = Column(
        BigInteger,
        ForeignKey("fsi_rolebutton_view.idx", ondelete="CASCADE"),
        primary_key=True,
    )
    role_id = Column(BigInteger, primary_key=True)
    type = Column(Enum(RestrictionType))

    def __repr__(self) -> str:
        return (
            f'<RBRestriction view_id="{self.view_id}" role_id="{self.role_id}" '
            f'type="{self.type}">'
        )

    def dump(self) -> dict:
        return {
            "view_id": self.view_id,
            "role_id": self.role_id,
            "type": self.type,
        }


class RBView(database.base):
    """Main database table which is holding together
    all other options and is used to configure and show
    RoleButton View.

    Attributes:
        idx: Unique ID of RB View
        guild_id: Guild ID of View
        unique: Whether user can choose more or one role
        message: Relationship pointing to RBMessage
        restrictions: Relationship pointing to RBRestriction
        options: Relationship pointing to RBOption (View select item)
    """

    __tablename__ = "fsi_rolebutton_view"

    idx = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger)
    unique = Column(Boolean)
    messages = relationship(
        lambda: RBMessage, cascade="all, delete", back_populates="rbview"
    )
    restrictions = relationship(lambda: RBRestriction, cascade="all, delete")
    options = relationship(lambda: RBOption, cascade="all, delete")

    @staticmethod
    def get_all(guild: discord.Guild = None) -> List[RBView]:
        query = session.query(RBView)

        if guild is not None:
            query.filter_by(guild_id=guild.id)

        return query.all()

    @staticmethod
    def create(guild: discord.Guild, unique: bool) -> Optional[RBView]:
        view = RBView(guild_id=guild.id, unique=unique)
        session.add(view)
        session.commit()

        return view

    @staticmethod
    def get(guild: discord.Guild, id: int) -> Optional[RBView]:
        query = session.query(RBView).filter_by(idx=id, guild_id=guild.id)

        return query.one_or_none()

    def add_message(self, message: discord.Message):
        check = [check for check in self.messages if check.message_id == message.id]

        if check:
            return

        rbmessage = RBMessage(
            message_id=message.id, channel_id=message.channel.id, view_id=self.idx
        )
        self.messages.append(rbmessage)
        session.commit()

    def add_restriction(self, role: discord.Role, type: RestrictionType):
        restriction = (
            session.query(RBRestriction)
            .filter_by(view_id=self.idx, role_id=role.id)
            .one_or_none()
        )

        if not restriction:
            restriction = RBRestriction(view_id=self.idx, role_id=role.id)

        restriction.type = type

        session.merge(restriction)
        session.commit()

    def remove_restriction(self, restriction):
        session.delete(restriction)
        session.commit()

    def remove_message(self, message: RBMessage):
        session.delete(message)
        session.commit()

    def add_option(self, option: RBOption):
        self.options.append(option)
        session.commit()

    def delete(self):
        session.delete(self)
        session.commit()

    def save(self):
        session.commit()

    def __repr__(self) -> str:
        return (
            f'<RBView idx="{self.idx}" guild_id="{self.guild_id}" '
            f'unique="{self.unique}" messages="{self.messages}" '
            f'restrictions="{self.restrictions}" options="{self.options}" >'
        )

    def dump(self) -> dict:
        return {
            "idx": self.idx,
            "guild_id": self.guild_id,
            "unique": self.unique,
            "messages": self.messages,
            "restrictions": self.restrictions,
            "options": self.options,
        }


class RBOption(database.base):
    """Represents one item in Select and is used to determine
    which roles or channels should be added to user.

    Attributes:
        idx: Unique ID of RB Option used for linking with Item
        view_id: ID of parent RB View
        label: Label of select
        description: Description of select
        emoji: Emoji showed in select
        items: Roles and channels assigned to Option
        oid: Order ID
    """

    __tablename__ = "fsi_rolebutton_option"

    idx = Column(Integer, primary_key=True, autoincrement=True)
    view_id = Column(Integer, ForeignKey("fsi_rolebutton_view.idx", ondelete="CASCADE"))
    label = Column(String)
    description = Column(String)
    emoji = Column(String)
    oid = Column(Integer, default=0)
    items = relationship(lambda: RBItem, cascade="all, delete")
    rbview = relationship(lambda: RBView, back_populates="options")

    def get(guild: discord.Guild, option_id: int) -> Optional[RBItem]:
        query = session.query(RBOption).filter_by(idx=option_id).one_or_none()

        if query is not None and query.rbview.guild_id != guild.id:
            return None

        return query

    def add_item(self, item: RBItem):
        self.items.append(item)
        session.commit()

    def save(self):
        session.commit()

    def delete(self):
        session.delete(self)
        session.commit()

    def __repr__(self) -> str:
        return (
            f'<RBOption idx="{self.idx}" view_id="{self.view_id}" '
            f'label="{self.label}" description="{self.description}" '
            f'emoji="{self.emoji}" items="{self.items}" '
            f'rbview="{self.rbview}" >'
        )

    def dump(self) -> dict:
        return {
            "idx": self.idx,
            "view_id": self.guild_id,
            "label": self.label,
            "description": self.description,
            "emoji": self.emoji,
            "items": self.items,
            "rbview": self.rbview,
        }


class RBItem(database.base):
    """This table is used to pair one or more roles and channels
    with RB option. Primary key is composed of option ID and Discord object ID.
    Type of Discord object is determined by :class:`DiscordType`

    Attributes:
        option_id: ID of parent Option
        discord_id: ID of Discord object
        discord_type: Type of Discord object
    """

    __tablename__ = "fsi_rolebutton_item"

    option_id = Column(
        Integer,
        ForeignKey("fsi_rolebutton_option.idx", ondelete="CASCADE"),
        primary_key=True,
    )
    discord_id = Column(BigInteger, primary_key=True)
    discord_type = Column(Enum(DiscordType))

    @staticmethod
    def get_by_option(option_id: int) -> List[RBItem]:
        query = session.query(RBItem).filter_by(option_id=option_id).all()

        return query

    def delete(self):
        session.delete(self)
        session.commit()

    def __repr__(self) -> str:
        return (
            f'<RBItem option_id="{self.option_id}" discord_id="{self.discord_id}" '
            f'discord_type="{self.discord_type}">'
        )

    def dump(self) -> dict:
        return {
            "option_id": self.option_id,
            "discord_id": self.discord_id,
            "discord_type": self.discord_type,
        }
