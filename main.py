import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import logging
import webserver

load_dotenv()
token = os.getenv("DISCORD_TOKEN")

handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")

intents = discord.Intents.default()
intents.members = True
intents.messages = True

CHANNEL_ID = 1427685251135569950  # Replace with your default channel ID
MESSAGE_ID_FILE = "message_id.txt"
ALLY_LIST_FILE = "ally_list.txt"
ENEMIES_LIST_FILE = "enemies_list.txt"

# Replace with Luna's Discord ID
ALLOWED_USER_ID = 1372549650225168436


# ---------- Helper Embeds ----------
def create_list_embed(title: str, items: list[str], color: discord.Color):
    """Create a neat formatted list embed."""
    if not items:
        desc = "*(no entries)*"
    else:
        desc = "\n".join(f"• {entry}" for entry in items)
    embed = discord.Embed(title=f"{title}", description=desc, color=color)
    return embed


def create_confirmation_embed(action: str, entry: str, color: discord.Color):
    """Simple uniform confirmation style."""
    return discord.Embed(
        title="✅ Success",
        description=f"{action}: **{entry}**",
        color=color
    )


def create_error_embed(message: str):
    """Error message embed."""
    return discord.Embed(
        title="❌ Error",
        description=message,
        color=discord.Color.red()
    )


# ---------- Helper Buttons ----------
class StatusButtons(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Allies", style=discord.ButtonStyle.success)
    async def show_allies(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = create_list_embed("Allies", self.bot.ally_list, discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Enemies", style=discord.ButtonStyle.danger)
    async def show_enemies(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = create_list_embed("Enemies", self.bot.enemies_list, discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)


class EditStatusButtons(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    async def wait_for_response(self, interaction, prompt):
        """Ask for text input and wait for response."""
        await interaction.followup.send(prompt, ephemeral=True)
        msg = await interaction.client.wait_for(
            "message", check=lambda m: m.author == interaction.user and m.channel == interaction.channel
        )
        return msg

    @discord.ui.button(label="Add Ally", style=discord.ButtonStyle.success)
    async def add_ally(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != ALLOWED_USER_ID:
            await interaction.response.send_message(embed=create_error_embed("You are not allowed to edit the status."), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        msg = await self.wait_for_response(interaction, "✏️ Enter the name to **add to Allies**:")
        entry = msg.content.strip()

        self.bot.ally_list.append(entry)
        await self.bot.update_embed()
        await msg.reply(embed=create_confirmation_embed("Added to Allies", entry, discord.Color.green()), mention_author=False)

    @discord.ui.button(label="Remove Ally", style=discord.ButtonStyle.danger)
    async def remove_ally(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != ALLOWED_USER_ID:
            await interaction.response.send_message(embed=create_error_embed("You are not allowed to edit the status."), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        msg = await self.wait_for_response(interaction, "✏️ Enter the name to **remove from Allies**:")
        entry = msg.content.strip()

        if entry in self.bot.ally_list:
            self.bot.ally_list.remove(entry)
            await self.bot.update_embed()
            await msg.reply(embed=create_confirmation_embed("Removed from Allies", entry, discord.Color.red()), mention_author=False)
        else:
            await msg.reply(embed=create_error_embed(f"Entry not found: {entry}"), mention_author=False)

    @discord.ui.button(label="Add Enemy", style=discord.ButtonStyle.success)
    async def add_enemy(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != ALLOWED_USER_ID:
            await interaction.response.send_message(embed=create_error_embed("You are not allowed to edit the status."), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        msg = await self.wait_for_response(interaction, "✏️ Enter the name to **add to Enemies**:")
        entry = msg.content.strip()

        self.bot.enemies_list.append(entry)
        await self.bot.update_embed()
        await msg.reply(embed=create_confirmation_embed("Added to Enemies", entry, discord.Color.red()), mention_author=False)

    @discord.ui.button(label="Remove Enemy", style=discord.ButtonStyle.danger)
    async def remove_enemy(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != ALLOWED_USER_ID:
            await interaction.response.send_message(embed=create_error_embed("You are not allowed to edit the status."), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        msg = await self.wait_for_response(interaction, "✏️ Enter the name to **remove from Enemies**:")
        entry = msg.content.strip()

        if entry in self.bot.enemies_list:
            self.bot.enemies_list.remove(entry)
            await self.bot.update_embed()
            await msg.reply(embed=create_confirmation_embed("Removed from Enemies", entry, discord.Color.red()), mention_author=False)
        else:
            await msg.reply(embed=create_error_embed(f"Entry not found: {entry}"), mention_author=False)


# ---------- Bot Definition ----------
class StatusBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="?", intents=intents)
        self.ally_list = []
        self.enemies_list = []

    async def on_ready(self):
        print(f"✅ Logged in as {self.user}")

        # Global + guild sync for instant visibility
        for guild in self.guilds:
            self.tree.clear_commands(guild=guild)
        await self.tree.sync()
        print("🌍 Synced global commands (for DMs)")
        for guild in self.guilds:
            try:
                await self.tree.sync(guild=guild)
                print(f"⚡ Instantly synced guild commands for {guild.name}")
            except Exception as e:
                print(f"Failed to sync guild {guild.name}: {e}")

        # Load data
        if os.path.exists(ALLY_LIST_FILE):
            with open(ALLY_LIST_FILE, "r") as f:
                self.ally_list = [line.strip() for line in f.readlines()]

        if os.path.exists(ENEMIES_LIST_FILE):
            with open(ENEMIES_LIST_FILE, "r") as f:
                self.enemies_list = [line.strip() for line in f.readlines()]

        # Persistent embed setup
        bot_message_id = None
        if os.path.exists(MESSAGE_ID_FILE):
            with open(MESSAGE_ID_FILE, "r") as f:
                bot_message_id = int(f.read().strip())

        channel = self.get_channel(CHANNEL_ID)
        if not channel:
            channel = await self.fetch_channel(CHANNEL_ID)

        if not bot_message_id:
            embed = discord.Embed(title="Status Board", color=discord.Color.blue())
            embed.add_field(name="Allies", value="*(no entries)*", inline=False)
            embed.add_field(name="Enemies", value="*(no entries)*", inline=False)
            msg = await channel.send(embed=embed)
            bot_message_id = msg.id
            with open(MESSAGE_ID_FILE, "w") as f:
                f.write(str(bot_message_id))
            print(f"Persistent embed sent with ID: {bot_message_id}")
        else:
            print(f"Found existing persistent message ID: {bot_message_id}")

        self.bot_message_id = bot_message_id
        await self.update_embed()

    async def update_embed(self):
        """Update the persistent embed message."""
        channel = self.get_channel(CHANNEL_ID)
        if not channel:
            channel = await self.fetch_channel(CHANNEL_ID)

        message = await channel.fetch_message(self.bot_message_id)
        embed = discord.Embed(title="Status Board", color=discord.Color.blurple())
        ally_content = "\n".join(f"• {entry}" for entry in self.ally_list) or "*(no entries)*"
        enemies_content = "\n".join(f"• {entry}" for entry in self.enemies_list) or "*(no entries)*"
        embed.add_field(name="Allies", value=ally_content, inline=False)
        embed.add_field(name="Enemies", value=enemies_content, inline=False)
        await message.edit(embed=embed)

        # Save data
        with open(ALLY_LIST_FILE, "w") as f:
            for entry in self.ally_list:
                f.write(f"{entry}\n")
        with open(ENEMIES_LIST_FILE, "w") as f:
            for entry in self.enemies_list:
                f.write(f"{entry}\n")


bot = StatusBot()


# ---------- Slash Commands ----------
@bot.tree.command(name="status", description="Shows the status board with Allies and Enemies.")
async def status(interaction: discord.Interaction):
    view = StatusButtons(bot)
    await interaction.response.send_message("📋 Select a category to view:", view=view, ephemeral=True)


@bot.tree.command(name="edit_status", description="Edit the status board (Luna only).")
async def edit_status(interaction: discord.Interaction):
    if interaction.user.id != ALLOWED_USER_ID:
        await interaction.response.send_message(embed=create_error_embed("You are not allowed to edit the status board."), ephemeral=True)
        return
    view = EditStatusButtons(bot)
    await interaction.response.send_message("🛠 Manage Allies and Enemies:", view=view, ephemeral=True)


# ---------- Run ----------
webserver.keepalive()
bot.run(token, log_handler=handler, log_level=logging.DEBUG)

