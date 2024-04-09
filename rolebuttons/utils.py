import re
from typing import List, Optional, Tuple, Union

import discord

from pie import i18n, logger

from .database import DiscordType, RBItem

EMOJI_REGEX = "^:[a-zA-Z0-9]+:$"

_ = i18n.Translator("modules/rolebuttons").translate
guild_log = logger.Guild.logger()


class RBUtils:
    @staticmethod
    def emoji_encode(
        bot: discord.Client, emoji: Union[discord.PartialEmoji, str]
    ) -> Optional[str]:
        """Gets emoji and translate it to str.

        If emoji is UTF-8 emoji, it returns it without change.
        If emoji is PartialEmoji, it return's ID if emoji is from bot's guilds
        If emoji is string `:emoji_name:` it tries to look up
        emoji by it's name in bot's DB.


        Args:
            bot: :class:`discord.Client` used to search for Emoji
            emoji: UTF-8 emoji, Discord emoji or :emoji_name: for lookup

        Returns:
        :class:`str` ID of emoji, UTF-8 emoji or None if emoji not in bot's DB.

        """
        if isinstance(emoji, discord.PartialEmoji):
            found_emoji = discord.utils.get(bot.emojis, id=emoji.id)
            if not found_emoji:
                return None
            return str(found_emoji.id)
        elif re.match(EMOJI_REGEX, emoji):
            found_emoji = discord.utils.get(bot.emojis, name=emoji.replace(":", ""))
            if not found_emoji:
                return None
            return str(found_emoji.id)
        else:
            return emoji

    @staticmethod
    def emoji_decode(
        bot: discord.Client,
        emoji: str,
    ) -> Optional[Union[str, discord.Emoji, discord.PartialEmoji]]:
        """If emoji is ID, it tries to look it up in bot's emoji DB.
        Otherwise it returns the emoji untouched as string.

        Args:
            bot: :class:`discord.Client` used to search for Emoji
            emoji: UTF-8 emoji or emoji's ID

        Returns:
            UTF-8 emoji or Discord Emoji

        """
        if emoji is None:
            return None

        if not emoji.isdigit():
            return emoji

        found_emoji = discord.utils.get(bot.emojis, id=int(emoji))
        if found_emoji:
            return found_emoji
        else:
            return emoji

    @staticmethod
    async def process_items(
        items: List[RBItem], guild: discord.Guild
    ) -> Tuple[discord.Role, discord.abc.GuildChannel]:
        """Internal function to convert List of RBItem DB objects
        to Discord roles and channels.
        Args:
            items: List of :class:`RBItem` to process

        Returns:
            Tuple of Lists, first containing roles, second containing Channels
        """
        roles = []
        channels = []

        for item in items:
            if item.discord_type == DiscordType.ROLE:
                role = guild.get_role(item.discord_id)
                if not role:
                    await guild_log.error(
                        None,
                        guild,
                        "There's invalid role ID {} in ReactionButton's database!".format(
                            item.discord_id
                        ),
                    )
                    continue
                roles.append(role)
            else:
                channel = guild.get_channel(item.discord_id)
                if not channel or not isinstance(channel, discord.abc.GuildChannel):
                    await guild_log.error(
                        None,
                        guild,
                        "There's invalid channel ID {} in ReactionButton's database!".format(
                            item.discord_id
                        ),
                    )
                    continue
                channels.append(channel)

        return roles, channels
