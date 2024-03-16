from __future__ import annotations

from typing import List, Tuple

import discord

from pie import i18n, logger

from .database import (
    RestrictionType,
    RBView,
    RBOption,
    RBItem,
)

from .utils import RBUtils as rbutils

_ = i18n.Translator("modules/fsi").translate
guild_log = logger.Guild.logger()


class OptionDropdown(discord.ui.Select):
    """Implementation of NextCord Select object used in RBView.
    It caches selected option for each combination of message and user,
    so it can be get from RBView and used to add / remove roles.

    This can actually be generalized and used as core object in future.

    Attributes:
        cache: :class:`Dictionary` holding selected values for (message_id, user_id) combination.
    """

    def __init__(
        self, bot: discord.Client, utx, custom_id: str, db_options: List[RBOption]
    ):
        """Inits SelectOptions based on list of RBOption DB objects.

        Args:
            utx: Translation context used for placeholder.
            custom_id: String used to identify Select
            db_options: List of RBOption DB objects
        """
        self.cache = {}

        options = []

        for db_option in db_options:
            option = discord.SelectOption(
                label=db_option.label,
                description=db_option.description,
                emoji=(
                    rbutils.emoji_decode(bot, db_option.emoji)
                    if db_option.emoji is not None
                    else None
                ),
                value=db_option.idx,
            )
            options.append(option)

        super().__init__(
            placeholder=_(utx, "Select role from list"),
            min_values=1,
            max_values=1,
            options=options,
            custom_id=custom_id,
        )

    def get(self, key: Tuple[int, int], defval) -> int:
        """Get value from cache by key (touple of Message and Member ID)

        Args:
            key: Tuple of Message and Member ID used as key
            defval: Default value which is returned if there's no value in cache

        Returns:
            Added/Updated config object
        """
        return self.cache.get(key, defval)

    async def callback(self, interaction: discord.Interaction):
        self.cache[(interaction.message.id, interaction.user.id)] = self.values[0]
        await interaction.response.defer()


class RBViewUI(discord.ui.View):
    """Persistant view used as UI for RoleButtons.
    There's only one RBView UI for one RBView DB object.
    Every instance is inicialized inside module and is
    linked by custom_id of each of it's object.
    This ID contains RBView DB object's unique ID which provides
    persistnace between bot restarts.

    This can actually be generalized and used as core object in future.

    Attributes:
        utx: Translation context based on guild
        dropdown: OptionDropdown used for getting selected option
    """

    def __init__(self, bot: discord.Client, view: RBView):
        """Creates translation context based on guild settings.
        Then inits OptionDropdown with all options user can choose,
        and buttons for add / remove.

        Args:
            view: RBView database object
        """

        self.utx = i18n.TranslationContext(view.guild_id, None)
        self.view = view
        self.bot = bot

        super().__init__(timeout=None)

        options = self.view.options

        self.dropdown = OptionDropdown(
            bot=self.bot,
            utx=self.utx,
            custom_id="rb_view_{}:select".format(self.view.idx),
            db_options=sorted(options, key=lambda x: (x.oid, x.label), reverse=False),
        )

        self.add_item(self.dropdown)

        addBtn = discord.ui.Button(
            label=_(self.utx, "Add"),
            style=discord.ButtonStyle.green,
            custom_id="rb_view_{}:add".format(self.view.idx),
        )

        removeBtn = discord.ui.Button(
            label=_(self.utx, "Remove"),
            style=discord.ButtonStyle.red,
            custom_id="rb_view_{}:remove".format(self.view.idx),
        )

        addBtn.callback = self.add
        removeBtn.callback = self.remove

        self.add_item(addBtn)
        self.add_item(removeBtn)

    async def _check_restrict(self, interaction: discord.Interaction):
        """Checks if user has one of allowed roles (if there are any)
        or if does not have disallowed role.

        If there's no restriction, returns True.
        If user has disallowed role, returns False.
        If there's no allowed role returns True.
        If there's allowed role and user is not member, returns False.

        Args:
            interaction: Interaction information

        Returns:
            :class:`bool`: True if user is allowed, False otherwise.
        """
        if not isinstance(interaction.user, discord.Member):
            return False

        if not self.view.restrictions:
            return True

        user = interaction.user
        is_allowed = None

        for restriction in self.view.restrictions:
            if restriction.type == RestrictionType.DISALLOW:
                if user.get_role(restriction.role_id):
                    return False
            else:
                if user.get_role(restriction.role_id):
                    is_allowed = True
                elif not is_allowed:
                    is_allowed = False

        return True if is_allowed is None else is_allowed

    async def add(self, interaction: discord.Interaction):
        """Button handler (callback) of button 'Add'
        Args:
            interaction: :class:`discord.Interaction` object
        """
        await self._process(interaction, add_items=True)

    async def remove(self, interaction: discord.Interaction):
        """Button handler (callback) of button 'Remove'
        Args:
            interaction: :class:`discord.Interaction` object
        """
        await self._process(interaction, add_items=False)

    async def _process(self, interaction: discord.Interaction, add_items: bool):
        """Internal function to process pressed button.
        Args:
            interaction: :class:`discord.Interaction` object
            add_items: :class:`bool` True if add items, False if remove
        """
        if not isinstance(interaction.user, discord.Member):
            return

        member = interaction.user
        guild = member.guild
        ctx = i18n.TranslationContext(guild.id, member.id)

        if not await self._check_restrict(interaction):
            await interaction.response.send_message(
                _(ctx, "You don't have permissions to use this Reaction Buttons"),
                ephemeral=True,
            )
            return

        value = self.dropdown.get((interaction.message.id, interaction.user.id), None)
        if value is None:
            await interaction.response.send_message(
                _(ctx, "You must select option first."), ephemeral=True
            )
            return

        await interaction.response.defer()

        items = RBItem.get_by_option(value)

        roles, channels = await rbutils.process_items(items, guild)

        if add_items:
            if self.view.unique:
                r_roles = set()
                r_channels = set()
                for option in self.view.options:
                    p_roles, p_items = await rbutils.process_items(option.items, guild)
                    r_roles.update(p_roles)
                    r_channels.update(p_items)

                remove_roles = r_roles.difference(roles)
                remove_channels = r_channels.difference(channels)
                await self._remove_items(
                    member,
                    [role for role in remove_roles if role in member.roles],
                    remove_channels,
                )

            if await self._add_items(member, roles, channels):
                await interaction.followup.send(
                    content=_(ctx, "Roles and channels successfuly added."),
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    content=_(ctx, "Something went wrong."),
                    ephemeral=True,
                )
        else:
            if await self._remove_items(member, roles, channels):
                await interaction.followup.send(
                    content=_(ctx, "Roles and channels successfuly removed."),
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    content=_(ctx, "Something went wrong."),
                    ephemeral=True,
                )

    async def _add_items(
        self,
        member: discord.Member,
        roles: List[discord.Role],
        channels: List[discord.abc.GuildChannel],
    ) -> bool:
        """Internal function to add roles and permissions.
        Args:
            member: Affected :class:`discord.Member`
            roles: List of :class:`discord.Role` to add
            channels: List of :class:`discord.abc.GuildChannel` to add

        Returns:
            True if no error, False if Exception was raised.
        """
        for role in member.roles:
            if role in roles:
                roles.remove(role)

        try:
            await member.add_roles(*roles, reason="ReactionButtons")
            for channel in channels:
                overwrites = channel.overwrites
                if member in overwrites and overwrites[member].read_messages:
                    continue
                await channel.set_permissions(member, read_messages=True)
            return True
        except (discord.Forbidden, discord.HTTPException) as ex:
            await guild_log.error(
                member,
                member.guild,
                "Exception occured during removing items in ReactionButtons.",
                exception=ex,
            )
            return False

    async def _remove_items(
        self,
        member: discord.Member,
        roles: List[discord.Role],
        channels: List[discord.abc.GuildChannel],
    ) -> bool:
        """Internal function to remove roles and permissions.
        Args:
            member: Affected :class:`discord.Member`
            roles: List of :class:`discord.Role` to remove
            channels: List of :class:`discord.abc.GuildChannel` to remove

        Returns:
            True if no error, False if Exception was raised.
        """
        for role in roles:
            if role not in member.roles:
                roles.remove(role)

        try:
            await member.remove_roles(*roles, reason="ReactionButtons")
            for channel in channels:
                overwrites = channel.overwrites
                if member not in overwrites or not overwrites[member].read_messages:
                    continue
                await channel.set_permissions(member, overwrite=None)
            return True
        except (discord.Forbidden, discord.HTTPException) as ex:
            await guild_log.error(
                member,
                member.guild,
                "Exception occured during removing items in ReactionButtons.",
                exception=ex,
            )
            return False
