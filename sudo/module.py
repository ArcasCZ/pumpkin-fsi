import tempfile

from typing import Union
from .objects import MessageModal

import discord
from discord import app_commands
from discord.ext import commands

from pie import i18n, utils, check

_ = i18n.Translator("modules/sudo").translate


class Sudo(commands.GroupCog, name="sudo"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    message = app_commands.Group(
        name="message", description="Sends / edits message as this bot."
    )

    # HELPER FUNCTIONS

    async def _get_message(
        self, utx: i18n.TranslationContext, inter: discord.Interaction, message_url: str
    ):
        try:
            parts = message_url.split("/")
            guild_id = int(parts[-3])
            channel_id = int(parts[-2])
            message_id = int(parts[-1])
        except (ValueError, IndexError):
            await inter.response.send_message(
                _(utx, "Incorrect message URL!"), ephemeral=True
            )
            return None

        dc_message: discord.Message = await utils.discord.get_message(
            self.bot, guild_id, channel_id, message_id
        )

        if dc_message is None:
            await inter.response.send_message(
                _(utx, "Message not found or not reachable!"), ephemeral=True
            )
            return None

        return dc_message

    # COMMANDS

    @check.acl2(check.ACLevel.SUBMOD)
    @message.command(name="send")
    async def sudo_message_send(
        self,
        inter: discord.Interaction,
        channel: Union[discord.TextChannel, discord.Thread],
    ):
        utx = i18n.TranslationContext(inter.guild.id, inter.user.id)
        message_modal = MessageModal(
            self.bot,
            title=_(utx, "Send message"),
            label=_(utx, "Message content:"),
            channel=channel,
        )
        await inter.response.send_modal(message_modal)

    @check.acl2(check.ACLevel.SUBMOD)
    @message.command(name="edit")
    async def sudo_message_edit(
        self,
        inter: discord.Interaction,
        message_url: str,
    ):
        utx = i18n.TranslationContext(inter.guild.id, inter.user.id)
        dc_message: discord.Message = await self._get_message(utx, inter, message_url)
        if not dc_message:
            return

        if len(dc_message.content) > 2000:
            await inter.response.send_message(
                _(utx, "Message content longer than 2000 characters!"), ephemeral=True
            )
            return
        message_modal = MessageModal(
            self.bot,
            title=_(utx, "Edit message"),
            label=_(utx, "Message content:"),
            message=dc_message,
            edit=True,
        )
        await inter.response.send_modal(message_modal)

    @check.acl2(check.ACLevel.SUBMOD)
    @message.command(name="resend")
    async def sudo_message_resend(
        self,
        inter: discord.Interaction,
        channel: Union[discord.TextChannel, discord.Thread],
        message_url: str,
    ):
        utx = i18n.TranslationContext(inter.guild.id, inter.user.id)
        dc_message: discord.Message = await self._get_message(utx, inter, message_url)
        if not dc_message:
            return

        if len(dc_message.content) > 2000:
            await inter.response.send_message(
                _(utx, "Message content longer than 2000 characters!"), ephemeral=True
            )
            return
        message_modal = MessageModal(
            self.bot,
            title=_(utx, "Edit message"),
            label=_(utx, "Message content:"),
            message=dc_message,
            channel=channel,
        )
        await inter.response.send_modal(message_modal)

    @check.acl2(check.ACLevel.SUBMOD)
    @message.command(name="download")
    async def sudo_message_download(self, inter: discord.Interaction, message_url: str):
        utx = i18n.TranslationContext(inter.guild.id, inter.user.id)
        dc_message: discord.Message = await self._get_message(utx, inter, message_url)

        if not dc_message:
            return

        file = tempfile.TemporaryFile(mode="w+")

        file.write(dc_message.content)

        filename = "message-{channel}-{message}.txt".format(
            channel=dc_message.channel.name, message=dc_message.id
        )

        file.seek(0)
        await inter.response.send_message(
            _(utx, "Message exported to TXT."),
            file=discord.File(fp=file, filename=filename),
            ephemeral=True,
        )
        file.close()


async def setup(bot) -> None:
    await bot.add_cog(Sudo(bot))
