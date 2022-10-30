from typing import List, Set

import discord
from discord.ext import commands

from pie import utils, check, i18n
from pie.utils.objects import ConfirmView, ScrollableEmbed

_ = i18n.Translator("modules/fsi").translate


class RoleManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # HELPER FUNCTIONS
    def _create_embeds(ctx, title: str, description: str) -> List[discord.Embed]:
        elements = []
        """Create embed for member list.
        Args:
            ctx: Command context.
            option: Item's title.
            description: list of items.
        Returns: :class:`discord.Embed` information embed
        """
        chunk_size = 15

        for i in range(0, len(description), chunk_size):

            page = utils.discord.create_embed(
                author=ctx.author,
                title=title,
                description="\n".join(description[i : i + chunk_size]),
            )

            elements.append(page)

        return elements

    def _get_intersection(role_base: str, role_remove: str) -> Set[discord.Member]:
        base_members = set(role_base.members)
        remove_members = set(role_remove.members)

        role_intersection = base_members & remove_members
        return role_intersection

    # MAIN
    @commands.guild_only()
    @commands.group(name="rolemanager")
    @check.acl2(check.ACLevel.MOD)
    async def rolemanager_(self, ctx):
        """
        Preview and remove selected roles from members with specified based role.
        """
        await utils.discord.send_help(ctx)

    @check.acl2(check.ACLevel.MOD)
    @rolemanager_.command(name="preview")
    async def rolemanager_preview(
        self, ctx, role_base: discord.Role, role_remove: discord.Role
    ):
        """
        List users to remove selected role from members with base role.
        """
        member_list = RoleManager._get_intersection(role_base, role_remove)

        if member_list:
            title = _(ctx, "Members with forbidden role")

            name_list = list(str(member) for member in member_list)

            embeds = RoleManager._create_embeds(
                ctx=ctx,
                title=title,
                description=name_list,
            )

            scrollable_embed = ScrollableEmbed(ctx, embeds)
            await scrollable_embed.scroll()

        else:
            await ctx.reply(_(ctx, "No member with this role"))

    @check.acl2(check.ACLevel.MOD)
    @rolemanager_.command(name="execute")
    async def rolemanager_execute(
        self, ctx, role_base: discord.Role, role_remove: discord.Role
    ):
        """
        Execute command to remove selected role from members with base role.
        """
        member_list = RoleManager._get_intersection(role_base, role_remove)

        if member_list:
            embed = discord.Embed(
                title=_(ctx, "REMOVE ROLE FROM MEMBERS"),
                description=_(
                    ctx,
                    "Are you sure you want from users with role: {role_base} remove role: {role_remove}?",
                ).format(role_base=role_base.mention, role_remove=role_remove.mention),
            )

            view = ConfirmView(ctx, embed)
            value = await view.send()
            if value:
                for member in member_list:
                    await member.remove_roles(role_remove)

                await ctx.send(_(ctx, "Successfully removed selected role."))
            else:
                await ctx.send(_(ctx, "Aborted."))

        else:
            await ctx.reply(_(ctx, "No member with this role"))


async def setup(bot) -> None:
    await bot.add_cog(RoleManager(bot))
