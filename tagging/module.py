from typing import List, Optional, Union

import discord
from discord.ext import commands

from pie import check, i18n, logger, utils

from .database import UserTag

_ = i18n.Translator("modules/fsi").translate
bot_log = logger.Bot.logger()
guild_log = logger.Guild.logger()


class Tagging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.guild_only()
    @check.acl2(check.ACLevel.MEMBER)
    @commands.group(name="tagging")
    async def tagging_(self, ctx):
        await utils.discord.send_help(ctx)

    @check.acl2(check.ACLevel.MOD)
    @tagging_.command(name="set")
    async def tagging_set(
        self,
        ctx,
        role: discord.Role,
        same_role: bool,
        limit: int,
        channel: discord.TextChannel = None,
    ):
        channel_name = channel.name if channel is not None else _(ctx, "(GLOBAL)")

        if UserTag.set(ctx.guild, role, channel, same_role, limit) is not None:
            message = _(
                ctx, "Set tag role {role} with vote limit {limit} in channel {channel}."
            )
            if same_role:
                message += " " + _(ctx, "User has to have this role.")
            await ctx.send(
                message.format(role=role.name, limit=limit, channel=channel_name)
            )
        else:
            await ctx.send(_(ctx, "Tag setting could not be created."))

    @check.acl2(check.ACLevel.MOD)
    @tagging_.command(name="unset")
    async def tagging_unset(
        self,
        ctx,
        role: discord.Role,
        channel: discord.TextChannel = None,
    ):
        deleted = UserTag.unset(ctx.guild, role, channel)

        if deleted == 0:
            await ctx.send(
                _(ctx, "No entry found for this role and channel combination!")
            )
        else:
            channel_name = channel.name if channel is not None else _(ctx, "(GLOBAL)")
            await ctx.send(
                _(
                    ctx, "Settings for role {role} and channel {channel} were unset."
                ).format(channel=channel_name, role=role.name)
            )

    @check.acl2(check.ACLevel.MEMBER)
    @tagging_.command(name="list")
    async def tagging_list(
        self, ctx, role: discord.Role = None, channel: discord.TextChannel = None
    ):
        query = UserTag.get_list(ctx.guild, role, channel)

        tags = []

        for item in query:
            user_tag = TagDummy()

            role = ctx.guild.get_role(item.role_id)
            user_tag.role = (
                role.name if role is not None else "({})".format(item.role_id)
            )

            channel = ctx.guild.get_channel(item.channel_id)
            user_tag.channel = (
                channel.name if channel is not None else "({})".format(item.channel_id)
            )

            user_tag.same_role = _(ctx, "Yes") if item.same_role else _(ctx, "No")

            user_tag.limit = item.limit

            tags.append(user_tag)

        table_pages: List[str] = utils.text.create_table(
            tags,
            {
                "idx": _(ctx, "ID"),
                "role": _(ctx, "Role"),
                "channel": _(ctx, "Channel"),
                "same_role": _(ctx, "Must have same role"),
                "limit": _(ctx, "Vote minimum"),
            },
        )

        for table_page in table_pages:
            await ctx.send("```" + table_page + "```")

    @commands.guild_only()
    @check.acl2(check.ACLevel.MEMBER)
    @commands.command(name="tag")
    async def tag(self, ctx, role: Union[discord.Role, str], *, message: str):
        await utils.discord.delete_message(ctx.message)

        if isinstance(role, str):
            role_lookup = discord.utils.get(ctx.guild.roles, name=role)
            if role_lookup is None:
                await ctx.send(
                    _(ctx, "Role *{role}* not found!").format(
                        role=utils.text.sanitise(role)
                    )
                )
                return

            role = role_lookup

        tag = UserTag.get_valid(ctx.guild.id, role.id, ctx.channel.id)

        if tag is None or tag.limit < 1:
            await ctx.send(_(ctx, "Can't tag this role here."))
            return

        if tag.same_role:
            if role not in ctx.author.roles:
                await ctx.send(
                    _(ctx, "You must be member of this role before you can tag them!")
                )
                return

        if tag.limit < 2:
            await self._tag_role(ctx, role, message)
            return

        timeout = 300

        embed = utils.discord.create_embed(
            author=ctx.author,
            title=_(ctx, "Vote to send tag!"),
        )

        embed.add_field(
            name=_(ctx, "Started by"),
            value=ctx.author,
        )

        embed.add_field(name=_(ctx, "Tagged role"), value=role.name)

        embed.add_field(name=_(ctx, "Message"), value=message)

        embed.add_field(name=_(ctx, "Minimal votes"), value=str(tag.limit))

        embed.add_field(name=_(ctx, "Time limit"), value=str(timeout) + "s")

        vote = VoteView(ctx, embed, tag.limit, timeout=timeout, vote_author=True)

        value = await vote.send()

        if value is None:
            await ctx.send(
                _(ctx, "{mention}, your tag did not have enough supporters.").format(
                    mention=ctx.author.mention
                )
            )

        else:
            await self._tag_role(ctx, role, message)

    async def _tag_role(self, ctx: commands.Context, role: discord.Role, message: str):
        await ctx.send(
            (
                _(ctx, "**{user}** tagged {role} with this message:") + "\n\n{message}"
            ).format(user=ctx.author.display_name, role=role.mention, message=message),
            allowed_mentions=discord.AllowedMentions(roles=True),
        )

        await bot_log.debug(
            ctx.author,
            ctx.message.channel.id,
            "User {user} tagged role {role} in channel {channel}".format(
                user=ctx.author, role=role, channel=ctx.channel.name
            ),
        )


class VoteView(discord.ui.View):
    """Class for making voting embeds easy.
    The right way of getting response is first calling send() on instance,
    then checking instance attribute `value`.

    Attributes:
        value: True if confirmed, False if declined, None if timed out
        ctx: Context of command
        message: Vote message

    Args:
        ctx: The context for translational and sending purposes.
        embed: Embed to send.
        limit: Minimal votes.
        timeout: Number of seconds before timeout. `None` if no timeout
        delete: Delete message after answering / timeout
        vote_author: Auto vote for author


    To use import this object and create new instance:
    .. code-block:: python
        :linenos:

        from pie.utils.objects import VoteView

        ...

        embed = utils.discord.create_embed(
            author=reminder_user,
            title=Vote for your action.",
        )
        view = VoteView(ctx, embed)

        value = await view.send()

        if value is None:
            await ctx.send(_(ctx, "Voted timed out."))
        elif value:
            await ctx.send(_(ctx, "Vote passed."))
    """

    def __init__(
        self,
        ctx: commands.Context,
        embed: discord.Embed,
        limit: int,
        timeout: Union[int, float, None] = 300,
        delete: bool = True,
        vote_author: bool = False,
    ):
        super().__init__(timeout=timeout)
        self.value: Optional[bool] = None
        self.ctx = ctx
        self.embed = embed
        self.limit = limit
        self.voted = []
        self.delete = delete

        if vote_author:
            self.voted.append(ctx.author.id)

    async def send(self):
        """Sends message to channel defined by command context.
        Returns:
            True if confirmed in time, None if timed out
        """

        self.button = discord.ui.Button(
            label=_(self.ctx, "Yes") + " ({})".format(len(self.voted)),
            style=discord.ButtonStyle.green,
            custom_id="yes-button",
        )

        self.add_item(self.button)

        self.message = await self.ctx.send(embed=self.embed, view=self)
        await self.wait()

        if not self.delete:
            self.clear_items()
            await self.message.edit(embed=self.embed, view=self)
        else:
            try:
                try:
                    await self.message.delete()
                except (
                    discord.errors.HTTPException,
                    discord.errors.Forbidden,
                ):
                    self.clear_items()
                    await self.message.edit(embed=self.embed, view=self)
            except discord.errors.NotFound:
                pass
        return self.value

    async def interaction_check(self, interaction: discord.Interaction) -> None:
        """Gets called when interaction with any of the Views buttons happens."""
        if interaction.user.id in self.voted:
            await interaction.response.send_message(
                _(self.ctx, "You have already voted!"), ephemeral=True
            )
            return

        self.voted.append(interaction.user.id)

        if len(self.voted) >= self.limit:
            self.value = True
            self.stop()
            return

        await interaction.response.send_message(
            _(self.ctx, "Your vote has been casted."), ephemeral=True
        )

        self.button.label = _(self.ctx, "Yes") + " ({})".format(len(self.voted))

        await self.message.edit(embed=self.embed, view=self)

    async def on_timeout(self) -> None:
        """Gets called when the view timeouts."""
        self.value = None
        self.stop()


class TagDummy:
    pass


async def setup(bot) -> None:
    await bot.add_cog(Tagging(bot))
