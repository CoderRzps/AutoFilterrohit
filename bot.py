import sys
import glob
import importlib
from pathlib import Path
from pyrogram import idle
import logging
import logging.config
import time  
import asyncio
from pyrogram import Client, __version__
from pyrogram.raw.all import layer
from database.ia_filterdb import Media, Media2, tempDict, choose_mediaDB, db as clientDB
from database.users_chats_db import db
from info import *
from utils import temp
from typing import Union, Optional, AsyncGenerator
from pyrogram import types
from Script import script 
from datetime import date, datetime 
import pytz
from aiohttp import web
from plugins import web_server, check_expired_premium
from LucyBot import CodeflixBot
from util.keepalive import ping_server
from LucyBot.clients import initialize_clients

botStartTime = time.time()

# Logging setup
logging.config.fileConfig('logging.conf')
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("imdbpy").setLevel(logging.ERROR)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logging.getLogger("aiohttp").setLevel(logging.ERROR)
logging.getLogger("aiohttp.web").setLevel(logging.ERROR)

# Plugin import
ppath = "plugins/*.py"
files = glob.glob(ppath)

async def Lucy_start():
    print('\nInitializing Lucy Bot')
    
    # ✅ Properly await CodeflixBot.start()
    await CodeflixBot.start()

    # ✅ Get bot info
    bot_info = await CodeflixBot.get_me()
    CodeflixBot.username = bot_info.username

    # ✅ Initialize clients
    await initialize_clients()

    # ✅ Import plugins
    for name in files:
        with open(name) as a:
            patt = Path(a.name)
            plugin_name = patt.stem.replace(".py", "")
            plugins_dir = Path(f"plugins/{plugin_name}.py")
            import_path = "plugins.{}".format(plugin_name)
            spec = importlib.util.spec_from_file_location(import_path, plugins_dir)
            load = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(load)
            sys.modules["plugins." + plugin_name] = load
            print("Lucy Imported => " + plugin_name)

    # ✅ Start keepalive pings if on Heroku
    if ON_HEROKU:
        asyncio.create_task(ping_server())

    # ✅ Fetch banned users & chats
    b_users, b_chats = await db.get_banned()
    temp.BANNED_USERS = b_users
    temp.BANNED_CHATS = b_chats

    # ✅ Ensure indexes
    await Media.ensure_indexes()
    await Media2.ensure_indexes()

    # ✅ Check database storage
    stats = await clientDB.command('dbStats')
    free_dbSize = round(512-((stats['dataSize']/(1024*1024))+(stats['indexSize']/(1024*1024))), 2)

    if DATABASE_URI2 and free_dbSize < 62:
        tempDict["indexDB"] = DATABASE_URI2
        logging.info(f"Switching to Secondary DB (Only {free_dbSize}MB left in Primary)")
    elif not DATABASE_URI2:
        logging.error("Missing SECONDDB_URI! Add it now!")
        exit()
    else:
        logging.info(f"Using Primary DB ({free_dbSize}MB free)")

    await choose_mediaDB()

    # ✅ Store bot info in temp variables
    me = await CodeflixBot.get_me()
    temp.ME = me.id
    temp.U_NAME = me.username
    temp.B_NAME = me.first_name
    CodeflixBot.username = '@' + me.username

    # ✅ Check expired premium users
    CodeflixBot.loop.create_task(check_expired_premium(CodeflixBot))

    # ✅ Logging bot start
    logging.info(f"{me.first_name} (Pyrogram v{__version__}, Layer {layer}) started on {me.username}.")
    logging.info(LOG_STR)
    logging.info(script.LOGO)

    # ✅ Send bot restart message
    tz = pytz.timezone('Asia/Kolkata')
    today = date.today()
    now = datetime.now(tz)
    time_str = now.strftime("%H:%M:%S %p")
    await CodeflixBot.send_message(chat_id=LOG_CHANNEL, text=script.RESTART_TXT.format(today, time_str))

    # ✅ Start web server
    app = web.AppRunner(await web_server())
    await app.setup()
    bind_address = "0.0.0.0"
    await web.TCPSite(app, bind_address, PORT).start()

    # ✅ Keep bot running
    await idle()

# ✅ Properly start the bot
if __name__ == '__main__':
    try:
        asyncio.run(Lucy_start())
    except KeyboardInterrupt:
        logging.info('Service Stopped Bye 👋')
