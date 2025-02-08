import sys
import glob
import importlib
import asyncio
import logging
import logging.config
import time  
from pathlib import Path
from pyrogram import idle
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

# Logging setup
logging.config.fileConfig('logging.conf')
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("imdbpy").setLevel(logging.ERROR)
logging.getLogger("aiohttp").setLevel(logging.ERROR)
logging.getLogger("aiohttp.web").setLevel(logging.ERROR)

botStartTime = time.time()
ppath = "plugins/*.py"
files = glob.glob(ppath)

async def Lucy_start():
    loop = asyncio.get_running_loop()  # ✅ Ensure correct event loop
    
    print('\nInitializing Lucy Bot')
    await CodeflixBot.start()
    bot_info = await CodeflixBot.get_me()
    CodeflixBot.username = bot_info.username

    await initialize_clients()

    # ✅ Fix: Ensure async function is awaited
    b_users, b_chats = await asyncio.ensure_future(db.get_banned())
    temp.BANNED_USERS = b_users
    temp.BANNED_CHATS = b_chats

    await Media.ensure_indexes()
    await Media2.ensure_indexes()

    stats = await clientDB.command('dbStats')
    free_dbSize = round(512 - ((stats['dataSize']/(1024*1024)) + (stats['indexSize']/(1024*1024))), 2)

    if DATABASE_URI2 and free_dbSize < 62:
        tempDict["indexDB"] = DATABASE_URI2
        logging.info(f"Switching to Secondary DB, only {free_dbSize} MB left in Primary DB.")
    elif DATABASE_URI2 is None:
        logging.error("Missing SECONDDB_URI! Exiting...")
        exit()
    else:
        logging.info(f"Primary DB has {free_dbSize}MB left, using it for storage.")

    await choose_mediaDB()
    
    me = await CodeflixBot.get_me()
    temp.ME = me.id
    temp.U_NAME = me.username
    temp.B_NAME = me.first_name
    CodeflixBot.username = '@' + me.username
    CodeflixBot.loop.create_task(check_expired_premium(CodeflixBot))

    logging.info(f"{me.first_name} running Pyrogram v{__version__} (Layer {layer}) on @{me.username}")
    logging.info(LOG_STR)
    logging.info(script.LOGO)

    tz = pytz.timezone('Asia/Kolkata')
    today = date.today()
    now = datetime.now(tz)
    time_str = now.strftime("%H:%M:%S %p")
    await CodeflixBot.send_message(chat_id=LOG_CHANNEL, text=script.RESTART_TXT.format(today, time_str))

    # ✅ Fix: Import plugins correctly
    for name in files:
        with open(name) as a:
            patt = Path(a.name)
            plugin_name = patt.stem.replace(".py", "")
            plugins_dir = Path(f"plugins/{plugin_name}.py")
            import_path = f"plugins.{plugin_name}"
            spec = importlib.util.spec_from_file_location(import_path, plugins_dir)
            load = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(load)
            sys.modules["plugins." + plugin_name] = load
            print(f"Lucy Imported => {plugin_name}")

    if ON_HEROKU:
        asyncio.create_task(ping_server())

    # ✅ Web server setup
    app = web.AppRunner(await web_server())
    await app.setup()
    await web.TCPSite(app, "0.0.0.0", PORT).start()

    await idle()


if __name__ == '__main__':
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(Lucy_start())  # ✅ Fix: Correct event loop usage
    except KeyboardInterrupt:
        logging.info('Service Stopped Bye 👋')
