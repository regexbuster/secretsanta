import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
import logging
import sqlite3
import datetime
import random
import traceback

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

    cur.execute("CREATE TABLE IF NOT EXISTS events(guild_id, name, register_date, event_date, price_limit)")

    cur.execute("CREATE TABLE IF NOT EXISTS members(user_id, guild_id, status, irl_name, interests, partner_id)")

@santa.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You are missing permissions needed to run this command.", ephemeral=True)
    else:
        traceback.print_exception(error)
        await ctx.send("There was an error running this command.", ephemeral=True)

### Plan Event
def isFinalized(guild_id):
    cur.execute('SELECT 1 FROM members WHERE guild_id = ? AND partner_id IS NOT NULL LIMIT 1', (guild_id,))
    return cur.fetchone() is not None

def isPlanned(guild_id):
    cur.execute('SELECT 1 FROM events WHERE guild_id = ?', (guild_id,))
    return cur.fetchone() is not None

@santa.hybrid_command()
@commands.has_permissions(manage_guild=True)
@commands.guild_only()
async def plan(ctx, name: str, register_date: str, event_date: str, price_limit: str):
    if isPlanned(ctx.guild.id):
        await ctx.send("There is already an event planned.", ephemeral=True)
        return

    await ctx.defer()

    cur.execute(
        'INSERT INTO events (guild_id, name, register_date, event_date, price_limit) VALUES (?, ?, ?, ?, ?)',
        (ctx.guild.id, name, register_date, event_date, price_limit),
    )
    con.commit()

    cnt = 0
    for mem in ctx.channel.members:
        if mem.bot == False:
            cur.execute('INSERT INTO members (user_id, guild_id, status, irl_name, interests, partner_id) VALUES (?, ?, ?, ?, ?, ?)', (mem.id, ctx.guild.id, 1, "", "", None))
            cnt += 1
    con.commit()

    embed = discord.Embed(
        title=name,
        color=discord.Color.random(),
        timestamp=datetime.datetime.now(datetime.UTC)
    )
    embed.add_field(name="Register Date", value=register_date)
    embed.add_field(name="Event Date", value=event_date)
    embed.add_field(name="Price Limit", value=price_limit)

    res = cur.execute(f'SELECT * FROM members WHERE guild_id = {ctx.guild.id} AND status = 2')
    val = res.fetchall()
    mem = []
    if val is not None:
        for v in val:
            m = await getMember(ctx, v[0])
            if m is not None:
                mem.append(m.name)

    embed.add_field(name="Registered", value=", ".join(mem), inline=False)

    res = cur.execute(f'SELECT * FROM members WHERE guild_id = {ctx.guild.id} AND status = 1')
    val = res.fetchall()
    mem = []
    if val is not None:
        for v in val:
            m = await getMember(ctx, v[0])
            if m is not None:
                mem.append(m.name)

    embed.add_field(name="Tentative", value=", ".join(mem), inline=False)

    res = cur.execute(f'SELECT * FROM members WHERE guild_id = {ctx.guild.id} AND status = 0')
    val = res.fetchall()
    mem = []
    if val is not None:
        for v in val:
            m = await getMember(ctx, v[0])
            if m is not None:
                mem.append(m.name)

    embed.add_field(name="Opt-out", value=", ".join(mem), inline=False)
    
    embed.set_footer(text="")

    await ctx.send(embed=embed)

### Join Event
@santa.hybrid_command()
@commands.guild_only()
async def join(ctx, irl_name: str, interests: str):
    await ctx.defer(ephemeral=True)

    if not isPlanned(ctx.guild.id):
        await ctx.send("There is not an event to join.", ephemeral=True)
        return

    if isFinalized(ctx.guild.id):
        await ctx.send("The event has been finalized, you cannot join now.")
        return

    cur.execute(
        'UPDATE members SET status = 2, irl_name = ?, interests = ? WHERE user_id = ? AND guild_id = ?', (irl_name, interests, ctx.author.id, ctx.guild.id)
    )
    if cur.rowcount == 0:
        cur.execute(
            'INSERT INTO members (user_id, guild_id, status, irl_name, interests, partner_id) VALUES (?, ?, ?, ?, ?, ?)',
            (ctx.author.id, ctx.guild.id, 2, irl_name, interests, None),
        )
    con.commit()

    await ctx.send(f'Thanks for setting your irl_name: {irl_name} and interests: {interests}')

### Opt-Out of Event
@santa.hybrid_command(name="opt-out")
@commands.guild_only()
async def optout(ctx):
    await ctx.defer(ephemeral=True)

    if not isPlanned(ctx.guild.id):
        await ctx.send("There is not an event to opt-out of.", ephemeral=True)
        return

    if isFinalized(ctx.guild.id):
        await ctx.send("The event has been finalized, you cannot opt-out now.")
        return

    cur.execute(
        'UPDATE members SET status = 0, irl_name = \'\', interests = \'\' WHERE user_id = ? AND guild_id = ?', (ctx.author.id, ctx.guild.id)
    )
    if cur.rowcount == 0:
        cur.execute(
            'INSERT INTO members (user_id, guild_id, status, irl_name, interests, partner_id) VALUES (?, ?, ?, ?, ?, ?)',
            (ctx.author.id, ctx.guild.id, 0, "", "", None),
        )
    con.commit()

    await ctx.send("Thank you for opting out.")

### Info
async def getMember(ctx, user_id):
    member = ctx.guild.get_member(user_id)  # if cached

    if member is None:
        try:
            member = await ctx.guild.fetch_member(user_id)  # API call if not cached
        except discord.NotFound:
            member = None

    return member

@santa.hybrid_command()
@commands.guild_only()
async def info(ctx):
    await ctx.defer()

    if not isPlanned(ctx.guild.id):
        await ctx.send("There is not an event planned to provide info for. Run /plan before calling again.", ephemeral=True)
        return

    event = cur.execute('SELECT name, register_date, event_date, price_limit FROM events WHERE guild_id = ?',(ctx.guild.id,)).fetchone()

    embed = discord.Embed(
        title=event[0],
        color=discord.Color.random(),
        timestamp=datetime.datetime.now(datetime.UTC)
    )
    embed.add_field(name="Register Date", value=event[1])
    embed.add_field(name="Event Date", value=event[2])
    embed.add_field(name="Price Limit", value=event[3])

    res = cur.execute(f'SELECT * FROM members WHERE guild_id = {ctx.guild.id} AND status = 2')
    val = res.fetchall()
    mem = []
    if val is not None:
        for v in val:
            m = await getMember(ctx, v[0])
            if m is not None:
                mem.append(m.name)

    embed.add_field(name="Registered", value=", ".join(mem), inline=False)

    res = cur.execute(f'SELECT * FROM members WHERE guild_id = {ctx.guild.id} AND status = 1')
    val = res.fetchall()
    mem = []
    if val is not None:
        for v in val:
            m = await getMember(ctx, v[0])
            if m is not None:
                mem.append(m.name)

    embed.add_field(name="Tentative", value=", ".join(mem), inline=False)

    res = cur.execute(f'SELECT * FROM members WHERE guild_id = {ctx.guild.id} AND status = 0')
    val = res.fetchall()
    mem = []
    if val is not None:
        for v in val:
            m = await getMember(ctx, v[0])
            if m is not None:
                mem.append(m.name)

    embed.add_field(name="Opt-out", value=", ".join(mem), inline=False)
    
    embed.set_footer(text="")

    await ctx.send(embed=embed)

### Nudge
@santa.hybrid_command()
@commands.has_permissions(manage_guild=True)
@commands.guild_only()
async def nudge(ctx):
    if not isPlanned(ctx.guild.id):
        await ctx.send("There is not an event planned. You cannot nudge now.", ephemeral=True)
        return

    if isFinalized(ctx.guild.id):
        await ctx.send("The event has been finalized, you cannot nudge now.", ephemeral=True)
        return

    await ctx.defer()

    res = cur.execute(f'SELECT * FROM members WHERE guild_id = {ctx.guild.id} AND status = 1')
    val = res.fetchall()
    mem = []
    if val is not None:
        for v in val:
            mem.append(f'<@{v[0]}>')

    if len(mem) == 0:
        await ctx.send("Everyone has responded!")
        return

    await ctx.send("Hello " + ", ".join(mem) + f'!\n<@{ctx.author.id}> would like to remind you to register for the event. \nYou can do so by running `/join` or `/opt-out` !')

### Finalize Event
def make_pairs(ids):
    order = ids[:]
    random.shuffle(order)
    return {giver: order[(i + 1) % len(order)] for i, giver in enumerate(order)}

@santa.hybrid_command()
@commands.has_permissions(manage_guild=True)
@commands.guild_only()
async def finalize(ctx):
    if not isPlanned(ctx.guild.id):
        await ctx.send("There is not an event planned to finalize. Run /plan before calling again.", ephemeral=True)
        return

    if isFinalized(ctx.guild.id):
        await ctx.send("The event has been finalized, you cannot finalize again.", ephemeral=True)
        return

    await ctx.defer()

    rows = cur.execute('SELECT user_id, irl_name, interests FROM members WHERE guild_id = ? AND status = 2',(ctx.guild.id,)).fetchall()
    details = {user_id: (irl_name, interests) for user_id, irl_name, interests in rows}

    members = {}
    for user_id in details:
        m = await getMember(ctx, user_id)
        if m is not None:
            members[user_id] = m

    if len(members) < 2:
        await ctx.send("Not enough people to have an event. Try inviting more people or having more join!")
        return

    pairs = make_pairs(list(members))

    cur.executemany('UPDATE members SET partner_id = ? WHERE user_id = ? AND guild_id = ?',[(target, giver, ctx.guild.id) for giver, target in pairs.items()])
    con.commit()

    failed = []
    for giver, target in pairs.items():
        irl_name, interests = details[target]
        try:
            await members[giver].send(f'Your secret santa partner is {members[target].name} ({irl_name}), they like {interests}')
        except discord.HTTPException:
            failed.append(members[giver].mention)

    if failed:
        await ctx.send("Everyone who joined should have received a DM from me with your secret santa partner. Please let someone know if you registered and didn't. (Failed to send to " + ", ".join(failed) + " please run /repeat to get a message.)")
    else:
        await ctx.send("Everyone who joined should have received a DM from me with your secret santa partner. Please let someone know if you registered and didn't.")

### Repeat
@santa.hybrid_command()
@commands.guild_only()
async def repeat(ctx):
    if ctx.interaction is None:
        await ctx.send("Please use /repeat as a slash command so only you can see the answer.")
        return

    if not isFinalized(ctx.guild.id):
        await ctx.send("Partners haven't been assigned yet.", ephemeral=True)
        return

    await ctx.defer(ephemeral=True)

    row = cur.execute("SELECT partner_id FROM members WHERE user_id = ? AND guild_id = ?", (ctx.author.id, ctx.guild.id)).fetchone()
    if row is None:
        await ctx.send("You were never registered for the event!")
        return
    partner_id = row[0]
    if partner_id is None:
        await ctx.send("You do not have a partner!")
        return

    target = cur.execute("SELECT irl_name, interests FROM members WHERE user_id = ? AND guild_id = ?", (partner_id, ctx.guild.id)).fetchone()
    if target is None:
        await ctx.send(f"Your partner's record is missing (id {partner_id}). Let an admin know.")
        return

    m = await getMember(ctx, partner_id)
    if m is None:
        await ctx.send(f"Your partner seems to have left the server (id {partner_id}). Let an admin know.")
        return

    await ctx.send(f"Your secret santa partner is {m.name} ({target[0]}), they like {target[1]}")

### Cancel Event
@santa.hybrid_command()
@commands.has_permissions(manage_guild=True)
@commands.guild_only()
async def cancel(ctx, confirm: bool = False):
    if not isPlanned(ctx.guild.id):
        await ctx.send("There is no event to cancel.", ephemeral=True)
        return

    if not confirm:
        await ctx.send("This deletes the event and every pairing. Run again with confirm set to True.", ephemeral=True)
        return

    await ctx.defer(ephemeral=True)

    cur.execute('DELETE FROM members WHERE guild_id = ?', (ctx.guild.id,))
    cur.execute('DELETE FROM events WHERE guild_id = ?', (ctx.guild.id,))
    con.commit()

    await ctx.send("Event canceled. You can now use `/plan` to re-plan your event.")

##### DEVELOPMENT COMMANDS

### Print Table
@santa.hybrid_command()
@commands.is_owner()
async def table(ctx, table: str):
    await ctx.defer(ephemeral=True)

    for row in cur.execute(f'SELECT * FROM {table}'):
        print(row)

    await ctx.send("Check console")

### Sync (for slash command registering)
## Guild Sync (faster)
@santa.command()
@commands.is_owner()
async def gsync(ctx):
    await ctx.defer(ephemeral=True)

    santa.tree.copy_global_to(guild=ctx.guild)
    synced = await santa.tree.sync(guild=ctx.guild)

    await ctx.send(f"Synced {len(synced)} commands to this server")

## Full Sync (slower)
@santa.command()
@commands.is_owner()
async def sync(ctx):
    await ctx.defer(ephemeral=True)

    synced = await santa.tree.sync()

    await ctx.send(f"Synced {len(synced)} commands")

santa.run(os.getenv("BOT_TOKEN"), log_handler=handler, log_level=logging.DEBUG)