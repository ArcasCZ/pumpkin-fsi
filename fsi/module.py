import re

import discord
from discord.ext import commands, tasks

from pie import check, i18n, logger, utils

_ = i18n.Translator("modules/fsi").translate
guild_log = logger.Guild.logger()

FISH_REGEX = r"^je [cč]erstv[aá]"


class FSI(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.fish_cache = 0
        self.cleanup.start()

    @commands.command(aliases=["divocak", "jako"])
    @check.acl2(check.ACLevel.MEMBER)
    async def slovakize(self, ctx, *, message: str = None):
        """Slovakize message"""
        if message is None:
            text = "Moc kratky text brasko!"
        else:
            text = utils.text.sanitise(
                self._slovakize(message), limit=1900, escape=False
            )
        await ctx.send(
            f"**{utils.text.sanitise(ctx.author.display_name)}**\n>>> " + text
        )

        await utils.discord.delete_message(ctx.message)

    @commands.Cog.listener()
    async def on_message(self, message):
        """User interactions"""
        # Ignore DMs
        if not isinstance(message.channel, discord.TextChannel):
            return

        if re.match(FISH_REGEX, message.content, flags=re.IGNORECASE):
            await self._fish_reaction(message)

    # HELPER FUNCTIONS

    async def _fish_reaction(self, message):
        if self.fish_cache < 4:
            self.fish_cache += 1
            await message.channel.send("Není čerstvá!")

    def _slovakize(self, text: str) -> str:
        text = text.replace(".", "").replace("?", "").replace("!", "").replace(",", "")
        words = text.split()

        for idx, word in enumerate(words):
            if len(word) < 3:
                continue

            if word.lower() in ["som", "ako"]:
                continue

            if word.lower() == "jako":
                words[idx] = word + "oou"
                continue

            if not word[-1].isalpha():
                continue
            if word[-1] == "e":
                continue
            elif word[-1] == "o":
                words[idx] = word + "s"
                continue
            elif word[-1] in ["a", "i", "u", "y"]:
                words[idx] = word[:-1] + "os"
                continue

            words[idx] = word + "os"

        text = " ".join(words) + " šak povedz ty ne"
        return text

    @tasks.loop(seconds=30.0)
    async def cleanup(self):
        if self.fish_cache > 0:
            self.fish_cache -= 1


async def setup(bot) -> None:
    await bot.add_cog(FSI(bot))
