"""
Standalone Module
Checks the visibility of our rs forum recruitment thread periodically and
pings in the bot channel if it needs a bump for visibility.
"""
from bs4 import BeautifulSoup
from discord.ext import tasks, commands
import zerobot_common
import requests

def get_forum_thread(thread_url, attempts=0):
    """
    Fetches the forum thread webpage and returns its html as a string.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.190 Safari/537.36'
            }
        req_resp = requests.get(thread_url, headers=headers, timeout=10)
    except requests.exceptions.Timeout:
        if attempts > 5:
            zerobot_common.logfile.log(f"Failed to get forum thread : {thread_url}")
            return None
        return get_forum_thread(attempts=attempts+1)
    except Exception:
        if attempts > 5:
            zerobot_common.logfile.log(f"Failed to get forum thread : {thread_url}")
            return None
        return get_forum_thread(attempts=attempts+1)

    if (req_resp.status_code == requests.codes["ok"]):
        return req_resp.text

def thread_is_on_first_page(page_html):
    """
    Tries to check if the forum thread is on the first page.
    """
    parsed_html = BeautifulSoup(page_html, 'html.parser')

    page_number_object = parsed_html.body.find('input', class_="forum-pagination__input-number")
    try:
        page = int(page_number_object['value'])
    except ValueError:
        zerobot_common.logfile.log(
            f"cant parse page number from forum thread : {page_number_object}"
        )
    
    if page > 1:
        return False
    return True

@tasks.loop(hours=9, reconnect=False)
async def forumthread_check_scheduler(self):
    """
    Checks the forum thread every 9 hours.
    """
    thread_url = zerobot_common.forumthread
    forum_page_html = get_forum_thread(thread_url)
    if forum_page_html is None:
        await zerobot_common.bot_channel.send(
            "Could not check forum thread status :("
        )
        return
    if thread_is_on_first_page(forum_page_html):
        return
    else:
        await zerobot_common.bot_channel.send(
            f"<@&192301641221931008> the forum thread <{thread_url.replace(',thd','')}> needs a bump!"
        )

class ForumThreadCog(commands.Cog):
    """
    Handles all the commands for applications.
    """
    def __init__(self, bot):
        self.bot = bot

        # start forum thread check loop
        try:
            forumthread_check_scheduler.start(self)
        except RuntimeError:
            # loop already running, happens when reconnecting.
            pass