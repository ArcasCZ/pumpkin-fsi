from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy import BigInteger, Boolean, Column, Integer, or_

import discord

from pie.database import database, session


class UserTag(database.base):
    """Represents a database UserTag item for :class:`Tagging` module.

    Attributes:
        idx: The database ID.
        guild_id: ID of the guild.
        role_id: Tagged role ID.
        channel_id: Channel ID for config.
        same_role: If user has to have tagged role
        limit: Minimal votes for group tagging
    """

    __tablename__ = "fsi_tagging_usertag"

    idx = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger)
    role_id = Column(BigInteger)
    channel_id = Column(BigInteger)
    same_role = Column(Boolean)
    limit = Column(Integer)

    @staticmethod
    def set(
        guild: discord.Guild,
        role: discord.Role,
        channel: discord.TextChannel,
        same_role: bool,
        limit: Integer,
    ) -> UserTag:
        """Change settings for role

        Args:
            guild: Guild UserTag belongs to
            role: Role UserTag belongs to
            channel: Channel UserTag belongs to (or None)
            same_role: True if user has to have tagged role
            limit: Minimal votes for role tagging
        """

        user_tag = UserTag.get_exact(guild=guild, role=role, channel=channel)

        if user_tag is None:
            user_tag = UserTag(
                guild_id=guild.id,
                channel_id=channel.id if channel is not None else 0,
                role_id=role.id,
            )

        user_tag.same_role = same_role
        user_tag.limit = limit

        session.merge(user_tag)
        session.commit()

        return user_tag

    @staticmethod
    def unset(
        guild: discord.Guild, role: discord.Role, channel: discord.TextChannel
    ) -> int:
        query = (
            session.query(UserTag)
            .filter_by(
                guild_id=guild.id,
                role_id=role.id,
                channel_id=channel.id if channel is not None else 0,
            )
            .delete()
        )

        return query

    @staticmethod
    def get_exact(
        guild: discord.guild, role: discord.Role, channel: discord.TextChannel
    ) -> Optional[UserTag]:
        query = (
            session.query(UserTag)
            .filter_by(
                guild_id=guild.id,
                channel_id=channel.id if channel is not None else 0,
                role_id=role.id,
            )
            .one_or_none()
        )
        return query

    @staticmethod
    def get_valid(guild_id: int, role_id: int, channel_id: int) -> Optional[UserTag]:
        query = (
            session.query(UserTag)
            .filter_by(guild_id=guild_id, role_id=role_id)
            .filter(or_(UserTag.channel_id == channel_id, UserTag.channel_id == 0))
            .order_by(UserTag.channel_id.desc())
        )

        return query.first()

    @staticmethod
    def get_list(guild, role, channel) -> List[UserTag]:
        query = session.query(UserTag).filter_by(guild_id=guild.id)

        if role is not None:
            query.filter_by(role_id=role.id)

        if channel is not None:
            query.filter_by(channel_id=channel.id)

        return query.all()

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} "
            f"idx='{self.idx}' guild_id='{self.guild_id}' "
            f"role_id='{self.role_id}' channel_id='{self.channel_id}' "
            f"same_role='{self.same_role}' limit='{self.limit}'>"
        )

    def dump(self) -> Dict[str, int]:
        return {
            "idx": self.idx,
            "guild_id": self.guild_id,
            "role_id": self.role_id,
            "channel_id": self.channel_id,
            "same_role": self.same_role,
            "limit": self.limit,
        }
