from discord.ext import commands
from datetime import datetime

import zerobot_common
from logfile import LogFile

logfile = None

if zerobot_common.channel_manager_enabled:
    # load google sheets document that contains the actual channel sheets (tabs)
    channels_doc_name = zerobot_common.settings.get("channels_doc_name")
    channels_doc = zerobot_common.drive_client.open(channels_doc_name)

# kc options
# total, solak, telos, nex aod, yaka, bm, nex, rax, rots, rago nm+hm, kk, raksha solo+duo
# vindi, helwyr, furies, greg, zilyana, graardor, k'ril, kree :  nm+hm
# sanctum, masuta, seiryu - astellarn, verak, bsd - crassian, taraket, amba: nm + hm
# magister, legiones, qbd, jad, kiln, barrows, chaos, daggas, mole nm+hm, kbd, corp, kq, rexes
# time options
# solak duo or more, telos, nex aod, yaka, bm, nex solo or more, rax solo duo, rots, rago nm+hm duo or more, kk solo or more, raksha solo+duo
# vindi, helwyr, furies, greg, zilyana, graardor, k'ril, kree :  nm+hm
# sanctum, masuta, seiryu - astellarn, verak, bsd - crassian, taraket, amba: nm(duo/trio) + hm(solo)
# magister, legiones, qbd, jad, kiln, barrows, chaos, daggas, mole nm+hm, kbd, corp, kq, rexes
boss_name_parser = {
    "total": "total_kc",
    "totals": "total_kc",
    "total_kill": "total_kc",
    "total_kills": "total_kc",
    "combined": "total_kc",
    "combined_total": "total_kc",
    "combined_total_kill": "total_kc",
    "combined_total_kills": "total_kc",
    "aod_nex":"nex_aod",
    "aod":"nex_aod",
    "durzag":"beastmaster_durzag",
    "bm":"beastmaster_durzag",
    "yaka":"yakamaru",
    "raxx":"araxxi",
    "rots":"rise_of_the_six",
    "duo_solak":"solak_duo",
    "rago":"vorago",
    "duo_rago":"vorago_duo",
    "hm_rago":"vorago_hm",
    "ragohm":"vorago_hm",
    "duo_ragohm":"vorago_duo_hm",
    "duo_rago_hm":"vorago_duo_hm",
    "rago_hm_duo":"vorago_duo_hm",
    "solo_nex":"nex_solo",
    "solo_raksha":"raksha_solo",
    "kree":"kree_arra",
    "kril":"kril_tsutsaroth",
    "k'ril":"kril_tsutsaroth",
    "k'ril_tsutsaroth":"kril_tsutsaroth",
    "zil":"zilyana",
    "zilly":"zilyana",
    "graador":"general_graardor",
    "grardor":"general_graardor",
    "bandos":"general_graardor",
    "kk":"kalphite_king",
    "legios":"legiones",
    "jad":"tztok_jad",
    "kiln":"har_aken",
    "barrows":"barrows_brothers",
    "bros":"barrows_brothers",
    "chaos":"chaos_elemental",
    "elly":"chaos_elemental",
    "daggas":"dagganoth_kings",
    "kings":"dagganoth_kings",
    "mole":"giant_mole",
    "hm_mole":"giant_mole_hm",
    "corp":"corporeal_beast",
    "kbd":"king_black_dragon",
    "qbd":"queen_black_dragon",
    "kq":"kalphite_queen",
    "rexes":"rex_matriarchs",
    "matriarchs":"rec_matriarchs",
    "glacor": "arch_glacor_nm",
    "glacor hm": "arch_glacor_hm",
    "hm glacor": "arch_glacor_hm",
}

class SubmissionsCog(commands.Cog):
    """
    Handles all the commands for applications.
    """
    def __init__(self, bot):
        self.bot = bot
        global logfile
        logfile = LogFile(
            "logs/submissionslog",
            parent = zerobot_common.logfile,
            parent_prefix = "submissionslog"
        )
        logfile.log(f"Submissions cog loaded and ready.")
    
    @commands.command()
    async def submit(self, ctx, *args):
        """
        Submit a killtime or killcount, only works in submissions channel
        """
        if not(zerobot_common.permissions.check("submit", ctx)): return
    
        use_str = (
            "```Usage: -zbot submit boss_name killtime/killcount <proof=link> <others=name 2+name 3+...>\n"
            "  boss_name: name_of_boss (or total_kc)\n"
            "  killtime/killcount: number (12345) OR time as mm:ss (1:23) format\n"
            "  link: link to screenshot or video as proof\n"
            "     not needed if you upload directly to discord and type the command as a comment for it.\n"
            "  others: optional, you can add the names of the others for group killtimes\n\n"
            "Example: -zbot submit nex_aod 4:26 proof=https://www.youtube.com/watch?v=dQw4w9WgXcQ others=Sanshine+African Herb```"
        )
        xargs = " ".join(args)
        expected_args = 2
        if "proof=" in xargs:
            expected_args += 1
        if "others=" in xargs:
            others = " ".join(args[expected_args:]).replace("<","").replace(">","").replace("others=","")
            args = args[0:expected_args]

        # check for attachments
        proof_link = ""
        for att in ctx.message.attachments:
            proof_link += att.url + "\n"
        proof_link = proof_link[:-1]

        if len(args) < expected_args:
            await ctx.send("Not enough options! try again, add boss_name, killtime/killcount or proof.\n" + use_str)
            return
        boss_name = args[0].replace("-","_")
        boss_name = boss_name_parser.get(boss_name, boss_name)

        if ":" in args[1]:
            type = "killtime"
            # accepted time formats
            timeformat = "%M:%S"
            try:
                datetime.strptime(args[1], timeformat)
                value = args[1]
                value = (6 - len(value))*" " + value
            except Exception:
                await ctx.send(f"killtime: {args[1]} is not a mm:ss time (1:23)" + use_str)
                return
        else:
            type = "killcount"
            try:
                value = int(args[1])
                value = (6 - len(str(value)))*" " + str(value)
            except ValueError:
                await ctx.send(f"killcount: {args[1]} is not a number" + use_str)
                return
        if proof_link == "":
            proof_link += args[2].replace("<","").replace(">","").replace("proof=","")
        names = f"{ctx.author.display_name}+{others}"
        
        add_to_submit_sheet(type, boss_name, value, names, proof_link, ctx.message.content)
        await ctx.send(
            f"submitted as : `{boss_name} {type}:{value}     "
            f"{names}, proof: {proof_link}`\n"
            " It will be added to the channel after it's checked."
        )
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """
        This event is triggered for any message received, including our own.
        Must keep this efficient, return asap if irrelevant.
        """
        if (
            message.channel.id != zerobot_common.submissions_channel_id or
            self.bot.user.id == message.author.id or
            "-zbot submit" in message.content
        ):
            return
        
        # check for attachments
        proof_link = ""
        for att in message.attachments:
            proof_link += att.url + "\n"
        proof_link = proof_link[:-1]

        add_to_submit_sheet("","","",message.author.display_name,proof_link,message.content)

def add_to_submit_sheet(type, boss_name, value, names, proof_link, msg):
    zerobot_common.drive_connect()
    sheet = channels_doc.worksheet("submissions")
    top_row = 2
    values = [
        str(type),
        str(boss_name),
        str(value),
        str(names),
        str(proof_link),
        str(msg),
        f"1) {value}     {names}"
    ]
    sheet.insert_row(values, top_row, value_input_option = 'USER_ENTERED')