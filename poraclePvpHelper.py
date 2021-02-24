import mapadroid.utils.pluginBase
from flask import render_template, Blueprint
from mapadroid.madmin.functions import auth_required
import os
import sys
import time
import json
import logging
from threading import Thread
import pickle
import requests
import configparser
from mapadroid.utils.logging import get_logger, LoggerEnums, get_bind_name
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "PogoPvpData"))
from pogopvpdata import PokemonData  # noqa: E402


logger = get_logger(LoggerEnums.plugin)


class PoracleInterceptHandler(logging.Handler):
    def __init__(self, *args, **kwargs):
        try:
            self.log_section = kwargs['log_section']
            del kwargs['log_section']
        except KeyError:
            self.log_section = LoggerEnums.unknown
        try:
            self.log_identifier = kwargs['log_identifier']
            del kwargs['log_identifier']
        except KeyError:
            self.log_identifier = LoggerEnums.unknown
        super().__init__(*args, **kwargs)
        self.log_identifier = get_bind_name(self.log_section, self.log_identifier)

    def emit(self, record):
        with logger.contextualize(name=self.log_identifier):
            logger.opt(depth=6, exception=record.exc_info).log(record.levelname, record.getMessage())


logging.getLogger('pogopvpdata').setLevel(logging.INFO)
logging.getLogger('pogopvpdata').addHandler(PoracleInterceptHandler())


class poraclePvpHelper(mapadroid.utils.pluginBase.Plugin):
    """poraclePvpHelper plugin
    """
    def __init__(self, mad):
        super().__init__(mad)

        self._rootdir = os.path.dirname(os.path.abspath(__file__))
        sys.path.append(self._rootdir)

        self._mad = mad
        self.db = self._mad["db_wrapper"]
        self.logger = get_logger(LoggerEnums.plugin)
        self.wh = self._mad["webhook_worker"]

        self.statusname = self._mad["args"].status_name
        self._pluginconfig.read(self._rootdir + "/plugin.ini")
        self._versionconfig.read(self._rootdir + "/version.mpl")
        self.author = self._versionconfig.get("plugin", "author", fallback="unknown")
        self.url = self._versionconfig.get("plugin", "url", fallback="https://www.maddev.eu")
        self.description = self._versionconfig.get("plugin", "description", fallback="unknown")
        self.version = self._versionconfig.get("plugin", "version", fallback="unknown")
        self.pluginname = self._versionconfig.get("plugin", "pluginname", fallback="https://www.maddev.eu")
        self.staticpath = self._rootdir + "/static/"
        self.templatepath = self._rootdir + "/template/"

        # plugin specific
        if self.statusname in self._pluginconfig:
            self.logger.success("Applying specific config for status-name {}!", self.statusname)
            settings = self.statusname
        else:
            self.logger.info("Using generic settings on instance with status-name {}", self.statusname)
            settings = "settings"
        self.target = self._pluginconfig.get(settings, "target", fallback=None)
        self.interval = self._pluginconfig.getint(settings, "interval", fallback=30)
        self.ranklength = self._pluginconfig.getint(settings, "ranklength", fallback=100)
        self.maxlevel = self._pluginconfig.getint(settings, "maxlevel", fallback=50)
        self.precalc = self._pluginconfig.getboolean(settings, "precalc", fallback=False)
        self.saveData = self._pluginconfig.getboolean(settings, "savedata", fallback=True)
        self.encid_string = self._pluginconfig.getboolean(settings, "encidstring", fallback=True)

        self._routes = [
            ("/poraclePvpHelper_manual", self.manual),
        ]

        self._hotlink = [
            ("poraclePvpHelper Manual", "poraclePvpHelper_manual", "poraclePvpHelper Manual"),
        ]

        if self._pluginconfig.getboolean("plugin", "active", fallback=False):
            self._plugin = Blueprint(str(self.pluginname), __name__, static_folder=self.staticpath,
                                     template_folder=self.templatepath)

            for route, view_func in self._routes:
                self._plugin.add_url_rule(route, route.replace("/", ""), view_func=view_func)

            for name, link, description in self._hotlink:
                self._mad['madmin'].add_plugin_hotlink(name, self._plugin.name + "." + link.replace("/", ""),
                                                       self.pluginname, self.description, self.author, self.url,
                                                       description, self.version)

    def perform_operation(self):
        # do not change this part ▽▽▽▽▽▽▽▽▽▽▽▽▽▽▽
        if not self._pluginconfig.getboolean("plugin", "active", fallback=False):
            return False
        self._mad['madmin'].register_plugin(self._plugin)
        # do not change this part △△△△△△△△△△△△△△△

        if not self._mad["args"].webhook:
            self.logger.error("Webhook worker is required but not enabled. Please set 'webhook' in your config "
                              "and restart. Stopping the plugin.")
            return False

        # load your stuff now
        self.logger.success("poraclePvpHelper Plugin starting operations ...")
        poraclePvpHelper = Thread(name="poraclePvpHelper", target=self.poraclePvpHelper,)
        poraclePvpHelper.daemon = True
        poraclePvpHelper.start()

        updateChecker = Thread(name="poraclePvpHelperUpdates", target=self.update_checker,)
        updateChecker.daemon = True
        updateChecker.start()

        return True

    def _pickle_data(self, data):
        if self.saveData:
            try:
                with open("{}/.data.pickle".format(os.path.dirname(os.path.abspath(__file__))), "wb") as datafile:
                    pickle.dump(data, datafile, -1)
                    self.logger.success("Saved data to pickle file")
                    return True
            except Exception as e:
                self.logger.warning("Failed saving to pickle file: {}".format(e))
                return False
        else:
            return False

    def _is_update_available(self):
        update_available = None
        try:
            r = requests.get("https://raw.githubusercontent.com/crhbetz/mp-poraclePvpHelper/master/version.mpl")
            self.github_mpl = configparser.ConfigParser()
            self.github_mpl.read_string(r.text)
            self.available_version = self.github_mpl.get("plugin", "version", fallback=self.version)
        except Exception:
            return None

        try:
            from pkg_resources import parse_version
            update_available = parse_version(self.version) < parse_version(self.available_version)
        except Exception:
            pass

        if update_available is None:
            try:
                from distutils.version import LooseVersion
                update_available = LooseVersion(self.version) < LooseVersion(self.available_version)
            except Exception:
                pass

        if update_available is None:
            try:
                from packaging import version
                update_available = version.parse(self.version) < version.parse(self.available_version)
            except Exception:
                pass

        return update_available

    def update_checker(self):
        while True:
            self.logger.debug("poraclePvpHelper checking for updates ...")
            result = self._is_update_available()
            if result:
                self.logger.warning("An update of poraclePvpHelper from version {} to version {} is available!",
                                    self.version, self.available_version)
            elif result is False:
                self.logger.success("poraclePvpHelper is up-to-date! ({} = {})", self.version, self.available_version)
            else:
                self.logger.warning("Failed checking for updates!")
            time.sleep(3600)

    # copied from mapadroid/webhook/webhookworker.py
    def _payload_chunk(self, payload, size):
        if size == 0:
            return [payload]

        return [payload[x: x + size] for x in range(0, len(payload), size)]

    # copied from mapadroid/webhook/webhookworker.py + some variables adjusted
    def _send_webhook(self, payloads):
        if len(payloads) == 0:
            self.logger.debug2("Payload empty. Skip sending to webhook.")
            return

        # get list of urls
        webhooks = self.target.replace(" ", "").split(",")

        webhook_count = len(webhooks)
        current_wh_num = 1

        for webhook in webhooks:
            payload_to_send = []
            sub_types = "all"
            url = webhook.strip()

            if url.startswith("["):
                end_index = webhook.rindex("]")
                end_index += 1
                sub_types = webhook[:end_index]
                url = url[end_index:]

                for payload in payloads:
                    if payload["type"] in sub_types:
                        payload_to_send.append(payload)
            else:
                payload_to_send = payloads

            if len(payload_to_send) == 0:
                self.logger.debug2("Payload empty. Skip sending to: {} (Filter: {})", url, sub_types)
                continue
            else:
                self.logger.debug2("Sending to webhook url: {} (Filter: {})", url, sub_types)

            payload_list = self._payload_chunk(payloads, self._mad["args"].webhook_max_payload_size)

            current_pl_num = 1
            for payload_chunk in payload_list:
                self.logger.debug4("Python data for payload: {}", payload_chunk)
                self.logger.debug4("Payload: {}", json.dumps(payload_chunk))

                try:
                    response = requests.post(
                        url,
                        data=json.dumps(payload_chunk),
                        headers={"Content-Type": "application/json"},
                        timeout=5,
                    )

                    if response.status_code != 200:
                        self.logger.warning("Got status code other than 200 OK from webhook destination: {}",
                                            response.status_code)
                    else:
                        if webhook_count > 1:
                            whcount_text = " [wh {}/{}]".format(current_wh_num, webhook_count)
                        else:
                            whcount_text = ""

                        if len(payload_list) > 1:
                            whchunk_text = " [pl {}/{}]".format(current_pl_num, len(payload_list))
                        else:
                            whchunk_text = ""

                        self.logger.success("Successfully sent poraclePvpHelper data to webhook{}{}. Mons sent: {}",
                                            whchunk_text, whcount_text, len(payload_chunk))
                except Exception as e:
                    self.logger.warning("Exception occured while sending webhook: {}", e)

                current_pl_num += 1
            current_wh_num += 1

    def poraclePvpHelper(self):
        self.__last_check = int(time.time())
        if not self.target:
            self.logger.error("no webhook (target) defined in settings - what am I doing here? ;)")
            return False

        if os.path.isfile("{}/data.pickle".format(self._rootdir)):
            os.rename("{}/data.pickle".format(self._rootdir), "{}/.data.pickle".format(self._rootdir))
            self.logger.success("migrated data.pickle to .data.pickle (hidden file)")

        try:
            with open("{}/.data.pickle".format(self._rootdir), "rb") as datafile:
                data = pickle.load(datafile)
        except Exception as e:
            self.logger.debug("exception trying to load pickle'd data: {}".format(e))
            add_string = " - start initialization" if self.precalc else " - will calculate as needed"
            self.logger.warning(f"Failed loading previously calculated data{add_string}")
            data = None

        if not data:
            data = PokemonData(self.ranklength, self.maxlevel, precalc=self.precalc)
            self._pickle_data(data)

        if not data:
            self.logger.error("Failed aquiring PokemonData object! Stopping the plugin.")
            return False

        self.logger.success("PokemonData object aquired")

        w = 0
        while not self.wh and w < 12:
            w += 1
            self.logger.warning("waiting for the webhook worker to be initialized ...")
            time.sleep(10)
        if w > 11:
            self.logger.error("Failed trying to access the webhook worker with webhook enabled. Please contact "
                              "the developer.")
            return False

        while True:
            try:
                starttime = int(time.time())
                monsFromDb = self.db.webhook_reader.get_mon_changed_since(self.__last_check)
                payload = self.wh._WebhookWorker__prepare_mon_data(monsFromDb)
                for mon in payload:
                    if "individual_attack" in mon["message"]:
                        content = mon["message"]
                        if self.encid_string:
                            content["encounter_id"] = str(content["encounter_id"])
                        try:
                            form = content["form"]
                        except Exception:
                            form = 0
                        try:
                            great, ultra = data.getPoraclePvpInfo(content["pokemon_id"], form,
                                                                  content["individual_attack"],
                                                                  content["individual_defense"],
                                                                  content["individual_stamina"],
                                                                  content["pokemon_level"])
                        except Exception as e:
                            self.logger.warning("Failed processing mon #{}-{}. Skipping. Error: {}",
                                                content["pokemon_id"], form, e)
                            continue
                        if len(great) > 0:
                            mon["message"]["pvp_rankings_great_league"] = great
                        if len(ultra) > 0:
                            mon["message"]["pvp_rankings_ultra_league"] = ultra
                self._send_webhook(payload)

                if self.saveData and data.is_changed():
                    self._pickle_data(data)
                    data.saved()

            except Exception:
                self.logger.opt(exception=True).error("Unhandled exception in poraclePvpHelper! Trying to continue... "
                                                      "Please notify the developer!")
            self.__last_check = starttime
            time.sleep(self.interval)

    @auth_required
    def manual(self):
        return render_template("poraclePvpHelper_manual.html",
                               header="poraclePvpHelper manual", title="poraclePvpHelper manual"
                               )
