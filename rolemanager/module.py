from typing import List

import discord
from discord.ext import commands

from pie import utils, check, i18n
from pie.utils.objects import ConfirmView, ScrollableEmbed

_ = i18n.Translator("modules/fsi").translate

# HELPER FUNCTIONS
class RoleManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _create_embeds(ctx, title: str, description: str) -> List[discord.Embed]:
        elements = []
        """Create embed for member list.
        Args:
            ctx: Command context.
            option: Item's title.
            description: list of items.
        Returns: :class:`discord.Embed` information embed
        """
        chunked_list = list()
        chunk_size = 15

        for i in range(0, len(description), chunk_size):
            
            page = utils.discord.create_embed(
                author=ctx.author,
                title=title,
                description='\n'.join(description[i:i+chunk_size]),
                )
            
            chunked_list.append(description[i:i+chunk_size])

            elements.append(page)

        return elements

# MAIN
    @commands.guild_only()
    @commands.group(name="rolemanager")
    @check.acl2(check.ACLevel.MOD)
    async def rolemanager_(self, ctx):
        """ 
        Preview and remove selected roles from members with specified based role.

        preview [base_role] [role_to_remove]
        execute [base_role] [role_to_remove]

        """
        await utils.discord.send_help(ctx)

    @check.acl2(check.ACLevel.MOD)
    @rolemanager_.command(name="preview")
    async def rolemanager_preview(self, ctx, role_base: discord.Role, *, role_remove: discord.Role):
        """ 
        List all users with base role and selected role to remove.
        """
        
        if  set(role_base.members) & set(role_remove.members):

            title = _(ctx, "Members with forbidden role")

            member_list = list((str(member) for member in role_base.members and role_remove.members))

            embeds = RoleManager._create_embeds(
                ctx=ctx,
                title=title,
                description =member_list,
                )
        
        scrollable_embed = ScrollableEmbed(ctx, embeds)
        await scrollable_embed.scroll()

    @check.acl2(check.ACLevel.MOD)
    @rolemanager_.command(name="execute")
    async def rolemanager_execute(self, ctx, role_base: discord.Role, *, role_remove: discord.Role):
        """ 
        Execute command to remove selected role from members with base role.
        """
        if  set(role_base.members) & set(role_remove.members):

            embed = discord.Embed(
                title=_(ctx, "REMOVE ROLE FROM MEMBERS"),
                description=_(ctx, "Are you sure you want from users with role: {role_base} remove role: {role_remove}?").format(role_base=role_base.mention, role_remove=role_remove.mention)
            )
            
            view = ConfirmView(ctx, embed)
            value = await view.send()
            if value is None:
                await ctx.send(_(ctx, "Confirmation timed out."))
            elif value:

                for member in set(role_base.members) & set(role_remove.members):
                    await member.remove_roles(role_remove)

                await ctx.send(_(ctx, "Successfully removed selected role."))
            else:
                await ctx.send(_(ctx, "Aborted."))
        
        else:
            await ctx.reply(_(ctx, "No member with this role"))  


async def setup(bot) -> None:
    await bot.add_cog(RoleManager(bot))