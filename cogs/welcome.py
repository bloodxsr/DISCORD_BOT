import discord
from discord.ext import commands

class WelcomeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Cache welcome, rules and chat channels per guild to avoid repeated lookups
        self.guild_channels = {}

    async def cache_guild_channels(self, guild):
        # Cache channels if not already cached for this guild
        if guild.id not in self.guild_channels:
            welcome_channel = discord.utils.get(guild.text_channels, name="welcome")
            rules_channel = discord.utils.get(guild.text_channels, name="rules")
            chat_channel = discord.utils.get(guild.text_channels, name="chat")

            self.guild_channels[guild.id] = {
                "welcome": welcome_channel,
                "rules": rules_channel,
                "chat": chat_channel,
            }

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await self.cache_guild_channels(member.guild)
        channels = self.guild_channels[member.guild.id]
        welcome_channel = channels["welcome"]
        if not welcome_channel:
            return

        # Format join dates just once
        created_at = member.created_at.strftime("%B %d, %Y")
        joined_at = member.joined_at.strftime("%B %d, %Y") if member.joined_at else "Just now"

        welcome_message = (
            f" Welcome to **{member.guild.name}**, {member.mention}! \n\n"
            "Please read the rules and introduce yourself.\n"
            "If you need help, ask moderators or active members.\n"
            "Enjoy your stay! 🌟\n"
            f"**Account Created:** {created_at}\n"
            f"**Joined Server:** {joined_at}"
        )

        embed = discord.Embed(title="Welcome!", description=welcome_message, color=discord.Color.pink())
        embed.set_thumbnail(url=member.avatar.url if member.avatar else None)

        # Create WelcomeButtonsView with cached channels for this guild
        view = WelcomeButtonsView(member.guild, channels)

        try:
            await welcome_channel.send(embed=embed, view=view)
        except Exception as e:
            # Use logging in production - print here for simplicity
            print(f"Failed to send welcome message: {e}")


class WelcomeButtonsView(discord.ui.View):
    def __init__(self, guild, channels):
        super().__init__(timeout=None)
        self.guild = guild

        rules_channel = channels.get("rules")
        if rules_channel:
            rules_url = f"https://discord.com/channels/{guild.id}/{rules_channel.id}"
            self.add_item(discord.ui.Button(label="📖 Rules", style=discord.ButtonStyle.link, url=rules_url))

        chat_channel = channels.get("chat")
        if chat_channel:
            chat_url = f"https://discord.com/channels/{guild.id}/{chat_channel.id}"
            self.add_item(discord.ui.Button(label="Chat Here", style=discord.ButtonStyle.link, url=chat_url))

    @discord.ui.button(label="Show Help Commands", style=discord.ButtonStyle.primary, custom_id="welcome_help_btn")
    async def help_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        help_text = (
            "**Here are some commands you can use:**\n"
            "`!joke` - Makes the bot tell a joke\n"
            "`!ask` - Ask the bot a question\n"
            "`!ping` - Check the bot’s response time\n"
            "More commands coming soon! stay tuned!"
        )
        await interaction.response.send_message(help_text, ephemeral=True)

    @discord.ui.button(label="About", style=discord.ButtonStyle.success, custom_id="welcome_about_btn")
    async def about_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        about_text = (
            "**About this server:**\n"
            "Learn more about our mission, team, and projects!"
        )
        await interaction.response.send_message(about_text, ephemeral=True)

    @discord.ui.button(label="Perks", style=discord.ButtonStyle.danger, custom_id="welcome_perks_btn")
    async def perks_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        perks_text = (
            "**Server Perks:**\n"
            "Unlock special roles, exclusive chats, and more by participating."
        )
        await interaction.response.send_message(perks_text, ephemeral=True)


async def setup(bot):
    await bot.add_cog(WelcomeCog(bot))