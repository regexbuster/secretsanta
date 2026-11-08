import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
import logging
import sqlite3

load_dotenv()

con = sqlite3.connect("santa.db")
cur = con.cursor()

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

santa = commands.Bot(command_prefix='!', intents=intents)

@santa.event
async def on_ready():
    print(f'We have logged in as {santa.user}!')

    res = None 
    while res == None:
        res = cur.execute("SELECT name FROM sqlite_schema WHERE type='table' AND name='events';")

        if res.fetchone() is None:
            cur.execute("CREATE TABLE events(guild_id, name, register_date, event_date, price_limit)")

    print("Added event table")

    res = None 
    while res == None:
        res = cur.execute("SELECT name FROM sqlite_schema WHERE type='table' AND name='members';")

        if res.fetchone() is None:
            cur.execute("CREATE TABLE members(user_id, guild_id, status, irl_name, interests)")

    print("Added members table")

# @santa.event
# async def on_message(message):
#     if message.author == santa.user:
#         return

#     print(f'Message from {message.author}: {message.content}')

#     if "hello" in message.content.lower():
#         await message.channel.send("Hello!")

### Plan Event
# admin only command to setup a secret santa event
@santa.hybrid_command()
async def plan(ctx, name: str, register_date: str, event_date: str, price_limit: str):
    await ctx.defer()

    res = cur.execute("SELECT * FROM events WHERE guild_id = ?", (ctx.guild.id))
    if res.fetchone() is None:
        await ctx.send("You are already planning an event!")
        return

    cur.execute(
        'INSERT INTO events (guild_id, name, register_date, event_date, price_limit) VALUES (?, ?, ?, ?, ?)',
        (ctx.guild.id, name, register_date, event_date, price_limit),
    )
    con.commit()

    cnt = 0
    for mem in ctx.channel.members:
        if mem.bot == False:
            con.execute('INSERT INTO members (user_id, guild_id, status, irl_name, interests) VALUES (?, ?, ?, ?, ?)', (mem.id, ctx.guild.id, 1, "", ""))
            cnt += 1
    con.commit()

    await ctx.send(f'event name: {name}  register date: {register_date}  event date: {event_date}  price limit: {price_limit} and added {cnt} users to event')

### Join Event
@santa.hybrid_command()
async def join(ctx, irl_name: str, interests: str):
    await ctx.defer(ephemeral=True)

    cur.execute(
        'UPDATE members SET status = 2, irl_name = ?, interests = ? WHERE user_id = ? AND guild_id = ?', (irl_name, interests, ctx.author.id, ctx.guild.id)
    )
    con.commit()

    await ctx.send(f'Thanks for setting your irl_name: {irl_name} and interests: {interests}')

### Opt-Out of Event

### Info

### Status

### Nudge

### Finalize Event

### Repeat



##### DEVELOPMENT COMMANDS

### Print Table
@santa.hybrid_command()
@commands.is_owner()
async def table(ctx, table: str):
    for row in cur.execute(f'SELECT * FROM {table}'):
        print(row)
    await ctx.send("Check console")

### Sync (for slash command registering)
## Guild Sync (faster)
@santa.command()
@commands.is_owner()
async def gsync(ctx):
    santa.tree.copy_global_to(guild=ctx.guild)
    synced = await santa.tree.sync(guild=ctx.guild)
    await ctx.send(f"Synced {len(synced)} commands to this server")

## Full Sync (slower)
@santa.command()
@commands.is_owner()
async def sync(ctx):
    synced = await santa.tree.sync()
    await ctx.send(f"Synced {len(synced)} commands")

santa.run(os.getenv("BOT_TOKEN"), log_handler=handler, log_level=logging.DEBUG)