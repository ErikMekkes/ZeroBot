import requests
import json
import zerobot_common
from logfile import LogFile
from member import valid_profile_link
from exceptions import NotAProfileLink, SiteDisabledError, SiteConnectionError

# discord rank name -> site rank id
_site_rank_ids = {
    #"Leaders" : 274497,
    #"Co-Leader" : 274498,
    #"Clan-Coordinator" : 274499,
    #"Clan Issues" : 274501,
    #"Citadel Co" : 274502,
    #"Media Co" : 274500,
    #"Staff Member" : 274503,
    "MasterClass PvMer" : 276402,
    "Supreme PvMer" : 274504,
    "PvM Specialists" : 276401,
    "Elite Member" : 274505,
    "Veteran Member" : 274506,
    "Advanced Member" : 274507,
    "Full Member" : 274508,
    "Recruit" : 274509,
    "Guest" : 274510
    #"Retired member" : 275283,
    #"Kicked Member" : 276400
}

# site rank id -> site rank name
_site_rank_names = {
    274497 : "Leader",
    274498 : "Co-Leader",
    274499 : "Clan-Coordinator",
    274501 : "Clan Issues",
    274502 : "Citadel Co",
    274500 : "Media Co",
    274503 : "Staff Member",
    276402 : "MasterClass PvMer",
    274504 : "Supreme PvMer",
    276401 : "PvM Specialists",
    274505 : "Elite Member",
    274506 : "Veteran Member",
    274507 : "Advanced Member",
    274508 : "Full Member",
    274509 : "Recruit",
    274510 : "Registered Guest",
    275283 : "Retired member",
    276400 : "Kicked Member"
}

class SiteOps:
    """
    Clan site account operations.
    """
    def __init__(self):
        """
        New object for site access operations
        """
        self.session = requests.session()
        self.logfile = LogFile("logs/sitelog")
        self.logfile.log(f"New log started for site operations.")

        self.token = None
    def _signin(self):
        """
        Signs in to the clan site with site credentials.
        Assumes the user credentials have sufficient permissions on site.
        """
        _sign_in_url = zerobot_common.site_base_url + "/users/sign_in.json"
        sign_in_res = self.session.post(_sign_in_url, json=zerobot_common.site_login_credentials)
        self.token = sign_in_res.json()["user_session"]["authentication_token"]
        self.logfile.log(f"Logged in on site, token: {self.token}")
    def _signout(self):
        """
        Signs the current token out of the clan site.
        """
        _sign_out_url = zerobot_common.site_base_url + "/users/sign_out.json?auth_token="
        sign_out_res = self.session.delete(_sign_out_url + self.token)
        self.logfile.log(f"Logging out token: {self.token}, response code : {sign_out_res.status_code}")
        self.token = None
    def setrank_member(self, member, new_rank):
        """
        tries to set rank on site to specified rank.
        member : member including site profile link to edit.
        rank : new rank to assign, equal to discord rank format

        Requires signing in to make edits. Assumes the site profile link is valid and exists.
        """
        self.setrank(member.profile_link, new_rank)
        member.site_rank = new_rank
    def setrank(self, profile_link, rank):
        """
        tries to set rank on site to specified rank.
        profile_link : profile link with member id to edit
        rank : new rank to assign, equal to discord rank format

        Requires signing in to make edits.
        Assumes there are no issues if the profile link is valid.
        """
        if not zerobot_common.site_enabled:
            raise SiteDisabledError()
        if not valid_profile_link(profile_link):
            raise NotAProfileLink(
                f"invalid site profile : {profile_link}, can not set rank"
            )
        self._signin()
        update_user_url = profile_link + ".json?auth_token=" + self.token
        new_site_rank_id = _site_rank_ids.get(rank, 0)
        user_changes = {"member": {"rank_id": new_site_rank_id}}
        update_user_res = self.session.patch(
            update_user_url, json=user_changes
        )
        #TODO: account for timeouts, retries, removed user / bad responses?
        self.logfile.log(
            f"Updating user: {profile_link} to {rank} "
            f"on site : {update_user_res.status_code}"
        )
        self._signout()
    def getRank(self, profile_link, retries=0):
        """
        Returns the site rank of the user with this profile link.
        Does not require signing in.
        """
        if not zerobot_common.site_enabled:
            raise SiteDisabledError()
        if not valid_profile_link(profile_link):
            raise NotAProfileLink(
                f"invalid site profile : {profile_link}, can not set rank"
            )
        
        get_member_url = profile_link + ".json"
        try:
            get_member_res = self.session.get(get_member_url)
        except requests.exceptions.Timeout:
            # TODO: maybe limit this with retries as well
            return self.getRank(profile_link)
        
        if (get_member_res.status_code == requests.codes["ok"]):
            json_res = get_member_res.json()
            member = json_res["member"]
            rank = _site_rank_names.get(member["rank_id"],"")
            return rank
        else:
            if retries < 3:
                retries += 1
                return self.getRank(profile_link, retries)
            raise SiteConnectionError(
                f"Failed to get rank from site : {profile_link}"
            )
    def update_site_info(self, memberlist):
        """
        Updates site rank for all members in the memberlist. Uses their set
        profile link to retrieve their rank from the site.
        """
        for memb in memberlist:
            # dont need to check if member has no valid profile link
            if not valid_profile_link(memb.profile_link):
                memb.site_rank = ""
                continue

            # try to find current site rank of member
            try:
                memb.site_rank = self.getRank(memb.profile_link)
            except SiteDisabledError:
                memb.site_rank = ""
                continue
            except SiteConnectionError:
                # site is down or valid but incorrect / removed profile link.
                # TODO should split out these two
                memb.site_rank = ""
                memb.note3 += f" old site profile: {memb.profile_link}"
                memb.profile_link = "no site"
                continue