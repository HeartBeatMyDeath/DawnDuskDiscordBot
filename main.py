import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
import logging
import re
import webserver

load_dotenv()
token = os.getenv("DISCORD_TOKEN")

handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True

CHANNEL_ID = 1427685251135569950
ALLY_LIST_FILE = "ally_list.txt"
ENEMIES_LIST_FILE = "enemies_list.txt"
MESSAGE_ID_FILE = "message_id.txt"

ALLOWED_USER_ID = 1372549650225168436  # Luna’s Discord ID


# --- Helper functions ---
def escape_markdown(text: str) -> str:
    """Escape Discord markdown characters so names render properly."""
    if not text:
        return ""
    return re.sub(r"([\\`*_{}[\]()#+.!|-])", r"\\\1", text)


def format_list(title, items, emoji, color):
    """Return a neat-looking embed for Allies or Enemies."""
    if items:
        desc = "\n".join(f"{emoji} {escape_markdown(entry)}" for entry in items)
    else:
        desc = "*(no entries)*"
    return discord.Embed(title=title, description=desc, color=color)


# --- Bot ---
class StatusBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="?", intents=intents)
        self.ally_list = []
        self.enemies_list = []

    async def setup_hook(self):
        # Register commands here so they’re available globally
        self.tree.add_command(status_command)
        self.tree.add_command(edit_status_command)

    async def on_ready(self):
        print(f"✅ Logged in as {self.user}")

        # --- CLEANUP OLD COMMANDS ---
        print("🧹 Cleaning up old commands...")
        try:
            # Clear all global commands first
            await self.tree.sync()  # make sure we have the latest first
            self.tree.clear_commands(guild=None)

            # Then re-add only the current two
            self.tree.add_command(status_command)
            self.tree.add_command(edit_status_command)

            # Sync global (for DMs)
            synced_global = await self.tree.sync()
            print(f"🌍 Synced {len(synced_global)} global command(s) for DMs")

            # Clear + re-sync guild commands for instant updates
            for guild in self.guilds:
                self.tree.clear_commands(guild=guild)
                self.tree.add_command(status_command, guild=guild)
                self.tree.add_command(edit_status_command, guild=guild)
                await self.tree.sync(guild=guild)
                print(f"⚡ Synced for guild: {guild.name}")
        except Exception as e:
            print(f"❌ Error while cleaning commands: {e}")

        # Load lists from file
        if os.path.exists(ALLY_LIST_FILE):
            with open(ALLY_LIST_FILE, "r") as f:
                self.ally_list = [line.strip() for line in f.readlines()]

        if os.path.exists(ENEMIES_LIST_FILE):
            with open(ENEMIES_LIST_FILE, "r") as f:
                self.enemies_list = [line.strip() for line in f.readlines()]

        print("📋 Ally/Enemy lists loaded successfully.")

    async def update_embed(self):
        """Update the persistent message if it exists."""
        if not os.path.exists(MESSAGE_ID_FILE):
            return

        with open(MESSAGE_ID_FILE, "r") as f:
            message_id = int(f.read().strip())

        channel = self.get_channel(CHANNEL_ID)
        if not channel:
            channel = await self.fetch_channel(CHANNEL_ID)

        try:
            msg = await channel.fetch_message(message_id)
        except discord.NotFound:
            return

        embed = discord.Embed(title="🌅 When Dawn Reaches Dusk", color=discord.Color.blurple())
        ally_content = "\n".join(f"🟢 {escape_markdown(entry)}" for entry in self.ally_list) or "*(no entries)*"
        enemies_content = "\n".join(f"🔴 {escape_markdown(entry)}" for entry in self.enemies_list) or "*(no entries)*"
        embed.add_field(name="Allies", value=ally_content, inline=False)
        embed.add_field(name="Enemies", value=enemies_content, inline=False)

        await msg.edit(embed=embed)

        # Persist lists
        with open(ALLY_LIST_FILE, "w") as f:
            for entry in self.ally_list:
                f.write(f"{entry}\n")

        with open(ENEMIES_LIST_FILE, "w") as f:
            for entry in self.enemies_list:
                f.write(f"{entry}\n")


bot = StatusBot()


# --- Views ---
class StatusView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Allies", style=discord.ButtonStyle.success, emoji="🟢")
    async def show_allies(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = format_list("🟢 Allies", self.bot.ally_list, "•", discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Enemies", style=discord.ButtonStyle.danger, emoji="🔴")
    async def show_enemies(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = format_list("🔴 Enemies", self.bot.enemies_list, "•", discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)


class EditStatusView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    async def _check_luna(self, interaction: discord.Interaction):
        if interaction.user.id != ALLOWED_USER_ID:
            await interaction.response.send_message("❌ You are not allowed to edit the status.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Add Ally", style=discord.ButtonStyle.success, emoji="➕")
    async def add_ally(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_luna(interaction): return
        await interaction.response.send_modal(TextInputModal(self.bot, "Add Ally", "ally"))

    @discord.ui.button(label="Remove Ally", style=discord.ButtonStyle.secondary, emoji="➖")
    async def remove_ally(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_luna(interaction): return
        await interaction.response.send_modal(TextInputModal(self.bot, "Remove Ally", "ally_remove"))

    @discord.ui.button(label="Add Enemy", style=discord.ButtonStyle.danger, emoji="➕")
    async def add_enemy(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_luna(interaction): return
        await interaction.response.send_modal(TextInputModal(self.bot, "Add Enemy", "enemy"))

    @discord.ui.button(label="Remove Enemy", style=discord.ButtonStyle.secondary, emoji="➖")
    async def remove_enemy(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_luna(interaction): return
        await interaction.response.send_modal(TextInputModal(self.bot, "Remove Enemy", "enemy_remove"))


# --- Modal ---
class TextInputModal(discord.ui.Modal):
    def __init__(self, bot, title, mode):
        super().__init__(title=title)
        self.bot = bot
        self.mode = mode
        self.entry = discord.ui.TextInput(label="Enter name", placeholder="Type here...")
        self.add_item(self.entry)

    async def on_submit(self, interaction: discord.Interaction):
        value = self.entry.value.strip()
        if not value:
            await interaction.response.send_message("⚠️ Please enter a valid name.", ephemeral=True)
            return

        if self.mode == "ally":
            self.bot.ally_list.append(value)
            await interaction.response.send_message(f"✅ Added ally: {escape_markdown(value)}", ephemeral=True)
        elif self.mode == "ally_remove":
            if value in self.bot.ally_list:
                self.bot.ally_list.remove(value)
                await interaction.response.send_message(f"✅ Removed ally: {escape_markdown(value)}", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Ally not found.", ephemeral=True)
        elif self.mode == "enemy":
            self.bot.enemies_list.append(value)
            await interaction.response.send_message(f"✅ Added enemy: {escape_markdown(value)}", ephemeral=True)
        elif self.mode == "enemy_remove":
            if value in self.bot.enemies_list:
                self.bot.enemies_list.remove(value)
                await interaction.response.send_message(f"✅ Removed enemy: {escape_markdown(value)}", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Enemy not found.", ephemeral=True)

        await self.bot.update_embed()


# --- Commands ---
@app_commands.command(name="status", description="View the current Allies and Enemies")
async def status_command(interaction: discord.Interaction):
    view = StatusView(bot)
    embed = discord.Embed(
        title="🌅 When Dawn Reaches Dusk",
        description="Select a list to view below:",
        color=discord.Color.blurple(),
    )
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


@app_commands.command(name="edit_status", description="Edit the Allies and Enemies (Luna only)")
async def edit_status_command(interaction: discord.Interaction):
    if interaction.user.id != ALLOWED_USER_ID:
        await interaction.response.send_message("❌ You are not allowed to edit the status.", ephemeral=True)
        return

    view = EditStatusView(bot)
    embed = discord.Embed(
        title="⚙️ Edit Status Board",
        description="Use the buttons below to add or remove Allies and Enemies.",
        color=discord.Color.gold(),
    )
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# --- Run Bot ---
webserver.keep_alive()
bot.run(token, log_handler=handler, log_level=logging.DEBUG)


