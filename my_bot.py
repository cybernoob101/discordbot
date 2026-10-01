import os
from datetime import datetime, timezone
from pathlib import Path

import discord
from dotenv import load_dotenv

import config

load_dotenv(Path(__file__).resolve().parent / '.env')

token = os.environ.get('DISCORD_TOKEN', '').strip()
if not token:
    raise SystemExit(
        'Set DISCORD_TOKEN in .env (local) or Railway Variables (deploy). See .env.example.'
    )

LOG_FILE = 'joins.log'

# Optional: only welcome in specific server(s), comma-separated IDs
# e.g. $env:WELCOME_GUILD_IDS="123456789,987654321"
WELCOME_GUILD_IDS = {
    int(guild_id.strip())
    for guild_id in os.environ.get('WELCOME_GUILD_IDS', '').split(',')
    if guild_id.strip().isdigit()
}

def welcome_message(member: discord.Member) -> str:
    template = os.environ.get('WELCOME_MESSAGE', config.WELCOME_MESSAGE)
    return template.format(
        name=member.display_name,
        username=member.name,
        server=member.guild.name,
    )


def format_member_details(member: discord.Member) -> str:
    user = member
    created = user.created_at.isoformat() if user.created_at else 'unknown'
    joined = member.joined_at.isoformat() if member.joined_at else 'unknown'
    avatar = user.display_avatar.url if user.display_avatar else 'none'

    return (
        f'username={user.name}\n'
        f'  display_name={member.display_name}\n'
        f'  global_name={user.global_name}\n'
        f'  user_id={user.id}\n'
        f'  bot={user.bot}\n'
        f'  account_created={created}\n'
        f'  joined_server={joined}\n'
        f'  avatar={avatar}'
    )


class JoinWatcher(discord.Client):
    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print(f'Logging joins to console and {LOG_FILE}')
        print('Sending welcome DMs to new members (skips bots).')
        print('------')

        if not self.guilds:
            print('You are not in any servers. Join or create one, then restart.')
            return

        for guild in self.guilds:
            try:
                await guild.subscribe(member_updates=True)
                monitored = not WELCOME_GUILD_IDS or guild.id in WELCOME_GUILD_IDS
                status = 'welcome ON' if monitored else 'welcome OFF (not in WELCOME_GUILD_IDS)'
                print(f'Monitoring: {guild.name} ({guild.id}) — {status}')
            except Exception as exc:
                print(f'Could not subscribe to {guild.name}: {exc}')

        if WELCOME_GUILD_IDS:
            print(f'Welcome DMs limited to guild IDs: {", ".join(map(str, WELCOME_GUILD_IDS))}')
        else:
            print('Welcome DMs enabled for all servers you are in.')

        print('------')
        print('Waiting for new members... (only joins while this is running)')

    async def on_member_join(self, member: discord.Member):
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        header = f'[{timestamp}] New member in {member.guild.name}'
        body = format_member_details(member)
        entry = f'{header}\n{body}\n'

        print(entry, end='')

        with open(LOG_FILE, 'a', encoding='utf-8') as log:
            log.write(entry)

        if member.bot:
            print('  Skipped welcome DM (member is a bot).\n')
            return

        if WELCOME_GUILD_IDS and member.guild.id not in WELCOME_GUILD_IDS:
            print('  Skipped welcome DM (server not in WELCOME_GUILD_IDS).\n')
            return

        try:
            await member.send(welcome_message(member))
            print(f'  Welcome DM sent to {member.display_name}.\n')
        except discord.Forbidden:
            print(f'  Could not DM {member.display_name} (DMs closed or blocked).\n')
        except discord.HTTPException as exc:
            print(f'  Failed to DM {member.display_name}: {exc}\n')


client = JoinWatcher()
client.run(token)
